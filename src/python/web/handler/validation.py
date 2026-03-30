# Copyright 2024, RapidCopy Contributors, All rights reserved.

"""
Validation REST API handler.

Provides endpoints for:
- Getting validation status for all files
- Triggering validation for a specific file
- Retrying validation for a corrupt file
"""

from urllib.parse import unquote

from bottle import HTTPResponse

from common import overrides
from controller import Controller
from ..web_app import IHandler, WebApp
from ..serialize import SerializeValidation
from .controller import WebResponseActionCallback


class ValidationHandler(IHandler):
    """
    Handler for validation-related REST API endpoints.
    """

    def __init__(self, controller: Controller):
        self.__controller = controller

    @overrides(IHandler)
    def add_routes(self, web_app: WebApp):
        web_app.add_handler("/server/validation/status", self.__handle_get_status)
        web_app.add_handler("/server/validation/config", self.__handle_get_config)
        web_app.add_handler("/server/command/validate/<file_name>", self.__handle_action_validate)

    def __handle_get_status(self):
        """
        Get validation status for all model files.
        Returns JSON with validation state for each file.
        """
        model_files = self.__controller.get_model_files()

        # Filter to files with validation-related states or properties
        validation_statuses = []
        for file in model_files:
            # Include files that are validating, validated, corrupt, or have validation properties set
            from model import ModelFile

            if (
                file.state
                in (
                    ModelFile.State.VALIDATING,
                    ModelFile.State.VALIDATED,
                    ModelFile.State.CORRUPT,
                )
                or file.validation_progress is not None
            ):
                validation_statuses.append(
                    {
                        "name": file.name,
                        "state": file.state.name,
                        "progress": file.validation_progress,
                        "error": file.validation_error,
                        "corrupt_chunks": file.corrupt_chunks,
                    }
                )

        out_json = SerializeValidation.validation_status(validation_statuses)
        return HTTPResponse(body=out_json, content_type="application/json")

    def __handle_get_config(self):
        """
        Get current validation configuration.
        Returns JSON with validation settings.
        """
        # Get validation config from controller - we need to access it via the model files
        # For now, return a status indicating whether validation is enabled
        model_files = self.__controller.get_model_files()

        # Count files in various validation states
        validating_count = 0
        validated_count = 0
        corrupt_count = 0

        from model import ModelFile

        for file in model_files:
            if file.state == ModelFile.State.VALIDATING:
                validating_count += 1
            elif file.state == ModelFile.State.VALIDATED:
                validated_count += 1
            elif file.state == ModelFile.State.CORRUPT:
                corrupt_count += 1

        config_info = {
            "validating_count": validating_count,
            "validated_count": validated_count,
            "corrupt_count": corrupt_count,
        }

        out_json = SerializeValidation.validation_config(config_info)
        return HTTPResponse(body=out_json, content_type="application/json")

    def __handle_action_validate(self, file_name: str):
        """
        Request validation for a specific file.
        :param file_name: Name of the file to validate
        :return: HTTPResponse with result
        """
        # Value is double encoded
        file_name = unquote(file_name)

        command = Controller.Command(Controller.Command.Action.VALIDATE, file_name)
        callback = WebResponseActionCallback()
        command.add_callback(callback)
        self.__controller.queue_command(command)
        callback.wait()

        if callback.success:
            return HTTPResponse(body="Queued validation for file '{}'".format(file_name))
        else:
            return HTTPResponse(body=callback.error, status=400)
