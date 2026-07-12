import {Injectable} from "@angular/core";
import {HttpEvent, HttpHandler, HttpInterceptor, HttpRequest} from "@angular/common/http";
import {Observable} from "rxjs";

/**
 * ApiKeyInterceptor injects the X-Api-Key header into every outgoing
 * HTTP request to the backend (/server/*).
 *
 * The key is injected by the server into index.html's meta tag and picked up at
 * bootstrap (main.ts), then cached in sessionStorage. The SSE stream, which cannot
 * set headers, passes the same key as an ?apikey= query param instead.
 * An empty key means no header is injected.
 */
@Injectable()
export class ApiKeyInterceptor implements HttpInterceptor {
    static readonly STORAGE_KEY = "rapidcopy.api_key";

    static setApiKey(key: string) {
        // sessionStorage (not localStorage): the key is re-injected into the page
        // on every load, so it need not persist across browser sessions, and this
        // bounds its exposure to the current tab session.
        if (key) {
            sessionStorage.setItem(ApiKeyInterceptor.STORAGE_KEY, key);
        } else {
            sessionStorage.removeItem(ApiKeyInterceptor.STORAGE_KEY);
        }
    }

    static getApiKey(): string {
        return sessionStorage.getItem(ApiKeyInterceptor.STORAGE_KEY) || "";
    }

    intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
        const apiKey = ApiKeyInterceptor.getApiKey();
        // Use startsWith on the path so we only attach the key to our own backend
        // routes, not to any URL that merely contains "/server/" in a query string.
        if (apiKey && (req.url.startsWith("/server/") || req.url.startsWith("server/"))) {
            const authReq = req.clone({
                setHeaders: {"X-Api-Key": apiKey}
            });
            return next.handle(authReq);
        }
        return next.handle(req);
    }
}
