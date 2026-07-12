# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
import collections

from common import Config


class SerializeConfig:
    # Config keys (case-insensitive) whose values are secrets and must NEVER be
    # returned to a client. The seedbox password stays server-side; the web UI
    # receives the api_key via index.html injection, not through this endpoint.
    __SECRET_KEYS = frozenset({"remote_password", "api_key", "apikey"})

    @staticmethod
    def config(config: Config) -> str:
        config_dict = config.as_dict()

        # Make the section names lower case + redact secret values.
        keys = list(config_dict.keys())
        config_dict_lowercase = collections.OrderedDict()
        for key in keys:
            section = config_dict[key]
            if isinstance(section, dict):
                section = {
                    k: ("" if k.lower() in SerializeConfig.__SECRET_KEYS else v)
                    for k, v in section.items()
                }
            config_dict_lowercase[key.lower()] = section

        return json.dumps(config_dict_lowercase)
