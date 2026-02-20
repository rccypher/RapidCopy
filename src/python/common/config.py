# Copyright 2017, Inderpreet Singh, All rights reserved.

import configparser
from io import StringIO
import collections
from abc import ABC
from typing import Type, TypeVar, Callable, Any

from .error import AppError
from .persist import Persist, PersistError
from .types import overrides


def strtobool(val: str) -> bool:
    """
    Convert a string representation of truth to True or False.

    True values are: 'y', 'yes', 't', 'true', 'on', '1'
    False values are: 'n', 'no', 'f', 'false', 'off', '0'

    This replaces the deprecated distutils.util.strtobool which was
    removed in Python 3.12.
    """
    val = val.lower().strip()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError(f"Invalid boolean value: {val!r}")


class ConfigError(AppError):
    """
    Exception indicating a bad config value
    """

    pass


InnerConfigType = dict[str, str]
OuterConfigType = dict[str, InnerConfigType]


# Source: https://stackoverflow.com/a/39205612/8571324
T = TypeVar("T", bound="InnerConfig")


class Converters:
    @staticmethod
    def null(_: type[T], __: str, value: str) -> str:
        return value

    @staticmethod
    def int(cls: type[T], name: str, value: str) -> int:
        if not value:
            raise ConfigError("Bad config: {}.{} is empty".format(cls.__name__, name))
        try:
            val = int(value)
        except ValueError as e:
            raise ConfigError(
                "Bad config: {}.{} ({}) must be an integer value".format(cls.__name__, name, value)
            ) from e
        return val

    @staticmethod
    def bool(cls: type[T], name: str, value: str) -> bool:
        if not value:
            raise ConfigError("Bad config: {}.{} is empty".format(cls.__name__, name))
        try:
            val = strtobool(value)
        except ValueError as e:
            raise ConfigError("Bad config: {}.{} ({}) must be a boolean value".format(cls.__name__, name, value)) from e
        return val


class Checkers:
    @staticmethod
    def null(_: type[T], __: str, value: Any) -> Any:
        return value

    @staticmethod
    def string_nonempty(cls: type[T], name: str, value: str) -> str:
        if not value or not value.strip():
            raise ConfigError("Bad config: {}.{} is empty".format(cls.__name__, name))
        return value

    @staticmethod
    def int_non_negative(cls: type[T], name: str, value: int) -> int:
        if value < 0:
            raise ConfigError("Bad config: {}.{} ({}) must be zero or greater".format(cls.__name__, name, value))
        return value

    @staticmethod
    def int_positive(cls: type[T], name: str, value: int) -> int:
        if value < 1:
            raise ConfigError("Bad config: {}.{} ({}) must be greater than 0".format(cls.__name__, name, value))
        return value

    @staticmethod
    def int_bounded(min_val: int, max_val: int) -> Callable:
        """Factory: returns a checker that enforces min_val <= value <= max_val."""
        def _checker(cls: type[T], name: str, value: int) -> int:
            if value < min_val or value > max_val:
                raise ConfigError(
                    "Bad config: {}.{} ({}) must be between {} and {}".format(
                        cls.__name__, name, value, min_val, max_val
                    )
                )
            return value
        return _checker


class InnerConfig(ABC):
    """
    Abstract base class for a config section
    Config values are exposed as properties. They must be set using their native type.
    Internal utility methods are provided to convert strings to native types. These are
    only used when creating config from a dict.

    Implementation details:
    Each property has associated with is a checker and a converter function.
    The checker function performs boundary check on the native type value.
    The converter function converts the string representation into the native type.
    """

    class PropMetadata:
        """Tracks property metadata"""

        def __init__(self, checker: Callable, converter: Callable):
            self.checker = checker
            self.converter = converter

    # Global map to map a property to its metadata
    # Is there a way for each concrete class to do this separately?
    __prop_addon_map: collections.OrderedDict[property, "InnerConfig.PropMetadata"] = collections.OrderedDict()

    @classmethod
    def _create_property(cls, name: str, checker: Callable, converter: Callable) -> property:
        # noinspection PyProtectedMember
        prop = property(fget=lambda s: s._get_property(name), fset=lambda s, v: s._set_property(name, v, checker))
        prop_addon = InnerConfig.PropMetadata(checker=checker, converter=converter)
        InnerConfig.__prop_addon_map[prop] = prop_addon
        return prop

    def _get_property(self, name: str) -> Any:
        return getattr(self, "__" + name, None)

    def _set_property(self, name: str, value: Any, checker: Callable):
        # Allow setting to None for the first time
        if value is None and self._get_property(name) is None:
            setattr(self, "__" + name, None)
        else:
            setattr(self, "__" + name, checker(self.__class__, name, value))

    @classmethod
    def from_dict(cls: Type[T], config_dict: InnerConfigType) -> T:
        """
        Construct and return inner config from a dict
        Dict values can be either native types, or str representations
        :param config_dict:
        :return:
        """
        config_dict = dict(config_dict)  # copy that we can modify

        # Loop over all the property name, and set them to the value given in config_dict
        # Raise error if a matching key is not found in config_dict
        # noinspection PyCallingNonCallable
        inner_config = cls()
        property_map = {p: getattr(cls, p) for p in dir(cls) if isinstance(getattr(cls, p), property)}
        for name, _prop in property_map.items():
            if name not in config_dict:
                raise ConfigError("Missing config: {}.{}".format(cls.__name__, name))
            inner_config.set_property(name, config_dict[name])
            del config_dict[name]

        # Raise error if a key in config_dict did not match a property
        extra_keys = config_dict.keys()
        if extra_keys:
            raise ConfigError("Unknown config: {}.{}".format(cls.__name__, next(iter(extra_keys))))

        return inner_config

    def as_dict(self) -> InnerConfigType:
        """
        Return the dict representation of the inner config
        :return:
        """
        config_dict = collections.OrderedDict()
        cls = self.__class__
        my_property_to_name_map = {getattr(cls, p): p for p in dir(cls) if isinstance(getattr(cls, p), property)}
        # Arrange prop names in order of creation. Use the prop map to get the order
        # Prop map contains all properties of all config classes, so filtering is required
        all_properties = InnerConfig.__prop_addon_map.keys()
        for prop in all_properties:
            if prop in my_property_to_name_map:
                name = my_property_to_name_map[prop]
                config_dict[name] = getattr(self, name)
        return config_dict

    def has_property(self, name: str) -> bool:
        """
        Returns true if the given property exists, false otherwise
        :param name:
        :return:
        """
        try:
            return isinstance(getattr(self.__class__, name), property)
        except AttributeError:
            return False

    def set_property(self, name: str, value: Any):
        """
        Set a property dynamically
        Do a str conversion of the value, if necessary
        :param name:
        :param value:
        :return:
        """
        cls = self.__class__
        prop_addon = InnerConfig.__prop_addon_map[getattr(cls, name)]
        # Do the conversion if value is of type str
        native_value = prop_addon.converter(cls, name, value) if type(value) is str else value
        # Set the property, which will invoke the checker
        # noinspection PyProtectedMember
        self._set_property(name, native_value, prop_addon.checker)


# Useful aliases
IC = InnerConfig
# noinspection PyProtectedMember
PROP = InnerConfig._create_property


class Config(Persist):
    """
    Configuration registry
    """

    class General(IC):
        debug = PROP("debug", Checkers.null, Converters.bool)
        verbose = PROP("verbose", Checkers.null, Converters.bool)
        # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO, ignored if debug=True)
        log_level = PROP("log_level", Checkers.null, Converters.null)

        def __init__(self):
            super().__init__()
            self.debug = None
            self.verbose = None
            self.log_level = None

    class Lftp(IC):
        remote_address = PROP("remote_address", Checkers.string_nonempty, Converters.null)
        remote_username = PROP("remote_username", Checkers.string_nonempty, Converters.null)
        remote_password = PROP("remote_password", Checkers.string_nonempty, Converters.null)
        remote_port = PROP("remote_port", Checkers.int_positive, Converters.int)
        remote_path = PROP("remote_path", Checkers.string_nonempty, Converters.null)
        local_path = PROP("local_path", Checkers.string_nonempty, Converters.null)
        remote_path_to_scan_script = PROP("remote_path_to_scan_script", Checkers.string_nonempty, Converters.null)
        use_ssh_key = PROP("use_ssh_key", Checkers.null, Converters.bool)
        num_max_parallel_downloads = PROP("num_max_parallel_downloads", Checkers.int_positive, Converters.int)
        num_max_parallel_files_per_download = PROP(
            "num_max_parallel_files_per_download", Checkers.int_positive, Converters.int
        )
        num_max_connections_per_root_file = PROP(
            "num_max_connections_per_root_file", Checkers.int_positive, Converters.int
        )
        num_max_connections_per_dir_file = PROP(
            "num_max_connections_per_dir_file", Checkers.int_positive, Converters.int
        )
        num_max_total_connections = PROP("num_max_total_connections", Checkers.int_non_negative, Converters.int)
        use_temp_file = PROP("use_temp_file", Checkers.null, Converters.bool)
        # Rate limit for downloads: "0" = unlimited, or specify like "1M" (1 MB/s), "500K" (500 KB/s)
        rate_limit = PROP("rate_limit", Checkers.null, Converters.null)

        def __init__(self):
            super().__init__()
            self.remote_address = None
            self.remote_username = None
            self.remote_password = None
            self.remote_port = None
            self.remote_path = None
            self.local_path = None
            self.remote_path_to_scan_script = None
            self.use_ssh_key = None
            self.num_max_parallel_downloads = None
            self.num_max_parallel_files_per_download = None
            self.num_max_connections_per_root_file = None
            self.num_max_connections_per_dir_file = None
            self.num_max_total_connections = None
            self.use_temp_file = None
            self.rate_limit = None

    class Controller(IC):
        interval_ms_remote_scan = PROP("interval_ms_remote_scan", Checkers.int_positive, Converters.int)
        interval_ms_local_scan = PROP("interval_ms_local_scan", Checkers.int_positive, Converters.int)
        interval_ms_downloading_scan = PROP("interval_ms_downloading_scan", Checkers.int_positive, Converters.int)
        extract_path = PROP("extract_path", Checkers.string_nonempty, Converters.null)
        use_local_path_as_extract_path = PROP("use_local_path_as_extract_path", Checkers.null, Converters.bool)

        def __init__(self):
            super().__init__()
            self.interval_ms_remote_scan = None
            self.interval_ms_local_scan = None
            self.interval_ms_downloading_scan = None
            self.extract_path = None
            self.use_local_path_as_extract_path = None

    class Web(InnerConfig):
        port = PROP("port", Checkers.int_positive, Converters.int)
        # api_key: if empty/None, authentication is disabled (backward compatible)
        api_key = PROP("api_key", Checkers.null, Converters.null)

        def __init__(self):
            super().__init__()
            self.port = None
            self.api_key = None

    class AutoQueue(InnerConfig):
        enabled = PROP("enabled", Checkers.null, Converters.bool)
        patterns_only = PROP("patterns_only", Checkers.null, Converters.bool)
        auto_extract = PROP("auto_extract", Checkers.null, Converters.bool)

        def __init__(self):
            super().__init__()
            self.enabled = None
            self.patterns_only = None
            self.auto_extract = None

    class Validation(InnerConfig):
        # Enable/disable download validation
        enabled = PROP("enabled", Checkers.null, Converters.bool)
        # Checksum algorithm: xxh128, md5, sha256, sha1
        algorithm = PROP("algorithm", Checkers.string_nonempty, Converters.null)
        # Default chunk size in bytes (default: 10485760 = 10MB)
        default_chunk_size = PROP("default_chunk_size", Checkers.int_bounded(1 * 1024 * 1024, 500 * 1024 * 1024), Converters.int)
        # Minimum chunk size in bytes (default: 1048576 = 1MB)
        min_chunk_size = PROP("min_chunk_size", Checkers.int_bounded(64 * 1024, 100 * 1024 * 1024), Converters.int)
        # Maximum chunk size in bytes (default: 104857600 = 100MB)
        max_chunk_size = PROP("max_chunk_size", Checkers.int_bounded(1 * 1024 * 1024, 1024 * 1024 * 1024), Converters.int)
        # Validate chunks inline during download; corrupt chunks are re-downloaded via pget_range
        validate_after_chunk = PROP("validate_after_chunk", Checkers.null, Converters.bool)
        # Maximum retry attempts for corrupt chunks
        max_retries = PROP("max_retries", Checkers.int_bounded(0, 20), Converters.int)
        # Delay between retries in milliseconds
        retry_delay_ms = PROP("retry_delay_ms", Checkers.int_bounded(0, 60000), Converters.int)
        # Enable adaptive chunk sizing based on network conditions
        enable_adaptive_sizing = PROP("enable_adaptive_sizing", Checkers.null, Converters.bool)

        def __init__(self):
            super().__init__()
            self.enabled = None
            self.algorithm = None
            self.default_chunk_size = None
            self.min_chunk_size = None
            self.max_chunk_size = None
            self.validate_after_chunk = None
            self.max_retries = None
            self.retry_delay_ms = None
            self.enable_adaptive_sizing = None

    def __init__(self):
        self.general = Config.General()
        self.lftp = Config.Lftp()
        self.controller = Config.Controller()
        self.web = Config.Web()
        self.autoqueue = Config.AutoQueue()
        self.validation = Config.Validation()

    @staticmethod
    def _check_section(dct: OuterConfigType, name: str) -> InnerConfigType:
        if name not in dct:
            raise ConfigError("Missing config section: {}".format(name))
        val = dct[name]
        del dct[name]
        return val

    @staticmethod
    def _check_empty_outer_dict(dct: OuterConfigType):
        extra_keys = dct.keys()
        if extra_keys:
            raise ConfigError("Unknown section: {}".format(next(iter(extra_keys))))

    @classmethod
    @overrides(Persist)
    def from_str(cls, content: str) -> "Config":
        config_parser = configparser.ConfigParser()
        try:
            config_parser.read_string(content)
        except (configparser.MissingSectionHeaderError, configparser.ParsingError) as e:
            raise PersistError("Error parsing Config - {}: {}".format(type(e).__name__, str(e))) from e
        config_dict: dict[str, dict[str, str]] = {}
        for section in config_parser.sections():
            config_dict[section] = {}
            for option in config_parser.options(section):
                config_dict[section][option] = config_parser.get(section, option)
        return Config.from_dict(config_dict)

    @overrides(Persist)
    def to_str(self) -> str:
        config_parser = configparser.ConfigParser()
        config_dict = self.as_dict()
        for section in config_dict:
            config_parser.add_section(section)
            section_dict = config_dict[section]
            for key in section_dict:
                config_parser.set(section, key, str(section_dict[key]))
        str_io = StringIO()
        config_parser.write(str_io)
        return str_io.getvalue()

    @staticmethod
    def from_dict(config_dict: OuterConfigType) -> "Config":
        config_dict = dict(config_dict)  # copy that we can modify
        config = Config()

        config.general = Config.General.from_dict(Config._check_section(config_dict, "General"))
        config.lftp = Config.Lftp.from_dict(Config._check_section(config_dict, "Lftp"))
        config.controller = Config.Controller.from_dict(Config._check_section(config_dict, "Controller"))
        config.web = Config.Web.from_dict(Config._check_section(config_dict, "Web"))
        config.autoqueue = Config.AutoQueue.from_dict(Config._check_section(config_dict, "AutoQueue"))
        # Validation section is optional for backwards compatibility
        if "Validation" in config_dict:
            config.validation = Config.Validation.from_dict(Config._check_section(config_dict, "Validation"))
        else:
            # Use default validation config
            config.validation = Config.Validation.from_dict(
                {
                    "enabled": "True",
                    "algorithm": "xxh128",
                    "default_chunk_size": "52428800",
                    "min_chunk_size": "1048576",
                    "max_chunk_size": "104857600",
                    "validate_after_chunk": "True",
                    "max_retries": "3",
                    "retry_delay_ms": "1000",
                    "enable_adaptive_sizing": "True",
                }
            )

        Config._check_empty_outer_dict(config_dict)
        return config

    def as_dict(self) -> OuterConfigType:
        # We convert all values back to strings
        # Use an ordered dict to main section order
        config_dict = collections.OrderedDict()
        config_dict["General"] = self.general.as_dict()
        config_dict["Lftp"] = self.lftp.as_dict()
        config_dict["Controller"] = self.controller.as_dict()
        config_dict["Web"] = self.web.as_dict()
        config_dict["AutoQueue"] = self.autoqueue.as_dict()
        config_dict["Validation"] = self.validation.as_dict()
        return config_dict

    def has_section(self, name: str) -> bool:
        """
        Returns true if the given section exists, false otherwise
        :param name:
        :return:
        """
        try:
            return isinstance(getattr(self, name), InnerConfig)
        except AttributeError:
            return False
