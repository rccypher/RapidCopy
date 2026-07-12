# Copyright 2017, Inderpreet Singh, All rights reserved.

import unittest
from unittest.mock import MagicMock
import logging
import sys

from webtest import TestApp

from common import overrides, Status, Config
from controller import AutoQueuePersist
from web import WebAppBuilder


class BaseTestWebApp(unittest.TestCase):
    """
    Base class for testing web app
    Sets up the web app with mocks
    """
    @overrides(unittest.TestCase)
    def setUp(self):
        self.context = MagicMock()
        self.controller = MagicMock()

        # Mock the base logger
        logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)
        self.context.logger = logger

        # Model files
        self.model_files = []

        # Real status
        self.context.status = Status()

        # Real config with a known API key so auth is deterministic in tests
        self.context.config = Config()
        self.api_key = "test-api-key"
        self.context.config.web.api_key = self.api_key

        # Real auto-queue persist
        self.auto_queue_persist = AutoQueuePersist()

        # Capture the model listener
        def capture_listener(listener):
            self.model_listener = listener
            return self.model_files
        self.model_listener = None
        self.controller.get_model_files_and_add_listener = MagicMock()
        self.controller.get_model_files_and_add_listener.side_effect = capture_listener
        self.controller.remove_model_listener = MagicMock()

        # Mock get_model_files so _validate_filename passes for common test names
        def _make_model_file(name):
            mf = MagicMock()
            mf.name = name
            return mf
        _test_names = [
            "test1", "test2", "/value/with/slashes", " value with spaces",
            "value'with'singlequote", 'value"with"doublequote',
        ]
        self.controller.get_model_files = MagicMock(
            return_value=[_make_model_file(n) for n in _test_names]
        )

        # noinspection PyTypeChecker
        self.web_app_builder = WebAppBuilder(self.context,
                                             self.controller,
                                             self.auto_queue_persist)
        self.web_app = self.web_app_builder.build()
        # All requests carry the API key header so /server/* auth passes.
        self.test_app = TestApp(self.web_app, extra_environ={"HTTP_X_API_KEY": self.api_key})


class TestWebApp(BaseTestWebApp):
    def test_process(self):
        self.web_app.process()


class TestWebAppAuth(BaseTestWebApp):
    """The API-key auth gate on /server/* routes."""

    def test_missing_key_is_rejected(self):
        # A fresh client with no key header must be rejected on /server/* routes.
        no_key = TestApp(self.web_app)
        resp = no_key.get("/server/config/get", expect_errors=True)
        self.assertEqual(401, resp.status_int)

    def test_wrong_key_is_rejected(self):
        bad = TestApp(self.web_app, extra_environ={"HTTP_X_API_KEY": "not-the-key"})
        resp = bad.get("/server/config/get", expect_errors=True)
        self.assertEqual(401, resp.status_int)

    def test_correct_key_is_accepted(self):
        resp = self.test_app.get("/server/config/get")
        self.assertEqual(200, resp.status_int)

    def test_key_accepted_as_query_param_for_stream(self):
        # EventSource can't set headers, so the key may be supplied as ?apikey=
        no_key = TestApp(self.web_app)
        resp = no_key.get("/server/config/get?apikey=" + self.api_key)
        self.assertEqual(200, resp.status_int)

    def test_key_is_generated_when_absent(self):
        # Regression: with no configured key the app must GENERATE one and still
        # construct (bottle.Bottle blocks re-assigning an existing attribute, so a
        # naive double-assignment crashed here). The generated key is then enforced.
        self.context.config.web.api_key = None
        builder = WebAppBuilder(self.context, self.controller, self.auto_queue_persist)
        app = builder.build()  # must not raise
        self.assertTrue(self.context.config.web.api_key)  # a key was generated
        resp = TestApp(app).get("/server/config/get", expect_errors=True)
        self.assertEqual(401, resp.status_int)  # enforcement is active
