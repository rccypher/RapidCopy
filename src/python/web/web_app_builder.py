# Copyright 2017, Inderpreet Singh, All rights reserved.

from common import Context, PathPairManager, NetworkMountManager
from controller import Controller, AutoQueuePersist
from .web_app import WebApp
from .handler.stream_model import ModelStreamHandler
from .handler.stream_status import StatusStreamHandler
from .handler.controller import ControllerHandler
from .handler.server import ServerHandler
from .handler.config import ConfigHandler
from .handler.auto_queue import AutoQueueHandler
from .handler.stream_log import LogStreamHandler
from .handler.status import StatusHandler
from .handler.path_pairs import PathPairsHandler
from .handler.validation import ValidationHandler
from .handler.update import UpdateHandler
from .handler.mounts import MountsHandler
from .handler.logs import LogsHandler


class WebAppBuilder:
    """
    Helper class to build WebApp with all the extensions
    """

    def __init__(self, context: Context, controller: Controller, auto_queue_persist: AutoQueuePersist):
        self.__context = context
        self.__controller = controller

        self.controller_handler = ControllerHandler(controller)
        self.server_handler = ServerHandler(context)
        self.config_handler = ConfigHandler(context.config)
        self.auto_queue_handler = AutoQueueHandler(auto_queue_persist)
        self.status_handler = StatusHandler(context.status)
        self.validation_handler = ValidationHandler(controller)
        self.update_handler = UpdateHandler(context.logger)
        # Path pairs handler for multi-path support
        self.path_pairs_handler = None
        if context.path_pair_manager:
            self.path_pairs_handler = PathPairsHandler(context.path_pair_manager)
        # Network mounts handler for NFS/CIFS support
        self.mounts_handler = None
        if context.network_mount_manager:
            self.mounts_handler = MountsHandler(context.network_mount_manager, context.logger)
        # Log search handler (only available when log_dir is configured)
        self.logs_handler = None
        if context.args.log_dir:
            self.logs_handler = LogsHandler(log_dir=context.args.log_dir)

    def build(self) -> WebApp:
        web_app = WebApp(context=self.__context, controller=self.__controller)

        StatusStreamHandler.register(web_app=web_app, status=self.__context.status)

        LogStreamHandler.register(web_app=web_app, logger=self.__context.logger)

        ModelStreamHandler.register(web_app=web_app, controller=self.__controller)

        self.controller_handler.add_routes(web_app)
        self.server_handler.add_routes(web_app)
        self.config_handler.add_routes(web_app)
        self.auto_queue_handler.add_routes(web_app)
        self.status_handler.add_routes(web_app)
        self.validation_handler.add_routes(web_app)
        self.update_handler.add_routes(web_app)

        # Add path pairs routes if available
        if self.path_pairs_handler:
            self.path_pairs_handler.add_routes(web_app)

        # Add network mounts routes if available
        if self.mounts_handler:
            self.mounts_handler.add_routes(web_app)

        # Add log search routes if available
        if self.logs_handler:
            self.logs_handler.add_routes(web_app)

        web_app.add_default_routes()

        return web_app
