# Copyright 2017, Inderpreet Singh, All rights reserved.

from typing import Type, Callable, Optional
from abc import ABC, abstractmethod
import time

import time
import collections
import threading
import bottle
from bottle import static_file

from common import Context
from controller import Controller


class IHandler(ABC):
    """
    Abstract class that defines a web handler
    """

    @abstractmethod
    def add_routes(self, web_app: "WebApp"):
        """
        Add all the handled routes to the given web app
        :param web_app:
        :return:
        """
        pass


class IStreamHandler(ABC):
    """
    Abstract class that defines a streaming data provider
    """

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def get_value(self) -> str | None:
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @classmethod
    def register(cls, web_app: "WebApp", **kwargs):
        """
        Register this streaming handler with the web app
        :param web_app: web_app instance
        :param kwargs: args for stream handler ctor
        :return:
        """
        web_app.add_streaming_handler(cls, **kwargs)




class _RateLimiter:
    """
    Simple sliding-window rate limiter keyed by client IP.
    Default: 120 requests per 60 seconds per IP.
    Static assets (/dashboard, /, /<file>.js etc.) are exempt.
    """
    _API_PREFIX = "/server/"
    _WINDOW_SECONDS = 60
    _MAX_REQUESTS = 120

    def __init__(self):
        self._counts: dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._WINDOW_SECONDS
        with self._lock:
            if ip not in self._counts:
                self._counts[ip] = collections.deque()
            dq = self._counts[ip]
            # Evict old timestamps
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self._MAX_REQUESTS:
                return False
            dq.append(now)
            return True


class WebApp(bottle.Bottle):
    """
    Web app implementation
    """

    _STREAM_POLL_INTERVAL_IN_MS = 100

    def __init__(self, context: Context, controller: Controller):
        super().__init__()
        self.logger = context.logger.getChild("WebApp")
        self.__controller = controller
        self.__html_path = context.args.html_path
        self.__status = context.status
        self.logger.info("Html path set to: {}".format(self.__html_path))
        self.__stop = False
        self.__api_key: str = getattr(context.config.web, 'api_key', '') or ''
        self.__streaming_handlers: list[tuple[Type[IStreamHandler], dict]] = []

        # Security headers applied to every response
        @self.hook("after_request")
        def _set_security_headers():
            bottle.response.set_header("X-Content-Type-Options", "nosniff")
            bottle.response.set_header("X-Frame-Options", "DENY")
            bottle.response.set_header("X-XSS-Protection", "1; mode=block")
            bottle.response.set_header("Referrer-Policy", "strict-origin-when-cross-origin")
            bottle.response.set_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
            )
        self.__rate_limiter = _RateLimiter()

        # Security: auth + rate limit + CSRF on API endpoints
        @self.hook("before_request")
        def _before_request():
            req_path = bottle.request.path
            method = bottle.request.method

            # API key authentication (if configured)
            # Disabled when api_key is empty (backward compatible default)
            if self.__api_key and req_path.startswith(_RateLimiter._API_PREFIX):
                # SSE stream passes key as query param (EventSource can't set headers)
                if req_path == "/server/stream":
                    provided = bottle.request.query.get("api_key", "")
                else:
                    provided = (
                        bottle.request.get_header("X-Api-Key", "")
                        or bottle.request.query.get("api_key", "")
                    )
                if provided != self.__api_key:
                    bottle.response.set_header("WWW-Authenticate", "ApiKey")
                    bottle.abort(401, "Unauthorized: valid X-Api-Key header required.")

            # Rate limit all API endpoints
            if req_path.startswith(_RateLimiter._API_PREFIX):
                ip = bottle.request.environ.get("HTTP_X_FORWARDED_FOR", bottle.request.remote_addr)
                ip = ip.split(",")[0].strip()  # take leftmost IP if proxied
                if not self.__rate_limiter.is_allowed(ip):
                    bottle.abort(429, "Too many requests. Please slow down.")

            # CSRF: verify Origin/Referer header on state-changing requests.
            # GET/HEAD/OPTIONS are safe methods and exempt.
            # The streaming endpoint uses GET and is also exempt.
            if method in ("POST", "PUT", "DELETE", "PATCH") and req_path.startswith(_RateLimiter._API_PREFIX):
                host = bottle.request.get_header("Host", "")
                origin = bottle.request.get_header("Origin", "")
                referer = bottle.request.get_header("Referer", "")

                # Extract hostname from Origin or Referer
                def _host_from_url(url: str) -> str:
                    if "://" in url:
                        url = url.split("://", 1)[1]
                    return url.split("/")[0].split("?")[0]

                allowed = False
                if origin:
                    allowed = _host_from_url(origin) == host
                elif referer:
                    # Fall back to Referer if Origin not present (e.g. same-origin GET redirect)
                    allowed = _host_from_url(referer) == host
                else:
                    # No Origin or Referer — allow only if request looks local
                    # (direct API clients like curl on localhost are still valid)
                    remote = bottle.request.environ.get("REMOTE_ADDR", "")
                    allowed = remote in ("127.0.0.1", "::1")

                if not allowed:
                    bottle.abort(403, "CSRF check failed: Origin mismatch.")

        # Security: apply headers to every response
        @self.hook("after_request")
        def _set_security_headers():
            bottle.response.set_header("X-Content-Type-Options", "nosniff")
            bottle.response.set_header("X-Frame-Options", "DENY")
            bottle.response.set_header("X-XSS-Protection", "1; mode=block")
            bottle.response.set_header("Referrer-Policy", "strict-origin-when-cross-origin")
            bottle.response.set_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
            )

    def add_default_routes(self):
        """
        Add the default routes. This must be called after all the handlers have
        been added.
        :return:
        """
        # Streaming route
        self.get("/server/stream")(self.__web_stream)

        # Front-end routes
        self.route("/")(self.__index)
        self.route("/dashboard")(self.__index)
        self.route("/settings")(self.__index)
        self.route("/autoqueue")(self.__index)
        self.route("/logs")(self.__index)
        self.route("/about")(self.__index)
        # For static files
        self.route("/<file_path:path>")(self.__static)

    def add_handler(self, path: str, handler: Callable):
        self.get(path)(handler)

    def add_streaming_handler(self, handler: Type[IStreamHandler], **kwargs):
        self.__streaming_handlers.append((handler, kwargs))

    def process(self):
        """
        Advance the web app state
        :return:
        """
        pass

    def set_api_key(self, api_key: str):
        """Update the API key at runtime (e.g. after config change)."""
        self.__api_key = api_key or ""

    def stop(self):
        """
        Exit gracefully, kill any connections and clean up any state
        :return:
        """
        self.__stop = True

    def __index(self):
        """
        Serves the index.html static file
        :return:
        """
        return self.__static("index.html")

    # noinspection PyMethodMayBeStatic
    def __static(self, file_path: str):
        """
        Serves all the static files
        :param file_path:
        :return:
        """
        return static_file(file_path, root=self.__html_path)

    def __web_stream(self):
        # Initialize all the handlers
        handlers = [cls(**kwargs) for (cls, kwargs) in self.__streaming_handlers]

        try:
            # Setup the response header
            bottle.response.content_type = "text/event-stream"
            bottle.response.cache_control = "no-cache"

            # Call setup on all handlers
            for handler in handlers:
                handler.setup()

            # Get streaming values until the connection closes
            while not self.__stop:
                for handler in handlers:
                    # Process all values from this handler
                    while True:
                        value = handler.get_value()
                        if value:
                            yield value
                        else:
                            break

                time.sleep(WebApp._STREAM_POLL_INTERVAL_IN_MS / 1000)

        finally:
            self.logger.debug("Stream connection stopped by {}".format("server" if self.__stop else "client"))

            # Cleanup all handlers
            for handler in handlers:
                handler.cleanup()
