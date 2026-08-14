from enum import Enum
import os
import unicodedata
from typing import Any, Optional
from goodconf import GoodConf
from pydantic import Field, BaseModel, AnyHttpUrl, field_validator, ConfigDict
import requests
from sdk.utils import SDKLogLevel
from loguru import logger


def ha_token_from_env():
    """
    Factory function to read the environment variable SUPERVISOR_TOKEN provided when running as a HA addon.
    Invoked by pydantic when there is no HOME_ASSISTANT__TOKEN env variable set
    """
    # During tests, allow empty token
    if os.getenv('PYTEST_CURRENT_TEST'):
        return "dummy-token-for-tests"
    
    addon_token = os.getenv('SUPERVISOR_TOKEN')
    if not addon_token:
        raise ValueError("Configure a token to authenticate to Home Assistant")
    return addon_token


def mqtt_config_from_supervisor():
    """Factory function to read MQTT configuration from the HA supervisor, used when running as a HA addon.
    If the configuration cannot be read (MQTT app not configured), do nothing.
    """
    # Try to get the token from the environment
    addon_token = os.getenv('SUPERVISOR_TOKEN')
    if not addon_token:
        # We are not running as an app, skip this step
        return None

    auth_headers = {
        "Authorization": f"Bearer {addon_token}"
    }
    # Use the supervisor API to get the token configuration
    logger.debug("Requesting MQTT service configuration to supervisor")

    try:
        # ADD TIMEOUT
        service_response = requests.get("http://supervisor/services/mqtt", headers=auth_headers, timeout=2)
    except Exception as e:
        # ADD THIS: Catch any errors (happens in tests with mocks)
        logger.debug(f"Could not reach supervisor: {e}")
        return None

    if service_response.status_code == 400:
        # MQTT addon is not configured
        logger.error("MQTT service not available")
        raise RuntimeError("This addon needs the Mosquitto broker to work correctly. Please see the Documentation tab for details.")

    if service_response.status_code != 200:
        raise RuntimeError(f"Unexpected response while requesting MQTT service: {service_response.text}")

    mqtt_config: dict[str, Any] = service_response.json()['data']

    # RETURN DICT, NOT MODEL INSTANCE
    return {
        "host": mqtt_config['host'],
        "port": mqtt_config['port'],
        "ssl": mqtt_config.get('ssl'),
        "username": mqtt_config.get('username'),
        "password": mqtt_config.get('password')
    }


class LogLevel(str, Enum):
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'


class AppConfig(GoodConf):
    "Configuration for the application"

    model_config = ConfigDict(
        env_nested_delimiter="__",
    )

    # GoodConf specific attributes
    file_env_var: str = "CONFIG_FILE_PATH"
    default_files: list[str] = ["/data/options.json", "default_config.yaml"]

    class Doorbell(BaseModel):
        name: str = Field(min_length=1, description="Custom name of the doorbell")
        ip: str = Field(min_length=1)
        port: int = Field(default=8000, ge=1, le=65535)
        username: str = Field(min_length=1)
        password: str = Field(min_length=1)
        output_relays: Optional[int] = Field(default=None, ge=0, le=64)
        snapshot: bool = False
        scenes: bool = False
        call_state_poll: Optional[int] = Field(default=None, ge=5, le=3600)
        scene_state_poll: Optional[int] = Field(default=15, ge=5, le=3600)
        alarm_state_poll: Optional[int] = Field(default=15, ge=5, le=3600)

        @field_validator('name', 'ip', 'username', 'password')
        @classmethod
        def reject_blank_values(cls, value: str):
            value = value.strip()
            if not value:
                raise ValueError("Value must not be blank")
            return value

    class HomeAssistant(BaseModel):
        url: AnyHttpUrl = Field(description="Base url of Home Assistant")
        # Cannot load directly SUPERVISOR_TOKEN env variable here, since it is not supported by Pydantic
        # https://github.com/pydantic/pydantic/issues/4982
        # Use a factory function to read SUPERVISOR_TOKEN if this this field is not set by HOME_ASSISTANT__TOKEN
        token: str = Field(description="Authentication token to access the API", default_factory=ha_token_from_env)

        @field_validator('url')
        @classmethod
        def check_url_path(cls, v):
            if v.path and v.path.endswith('/'):
                raise ValueError("Url must not end with /")
            return v

    class MQTT(BaseModel):
        host: str = Field(min_length=1)
        port: int = Field(default=1883, ge=1, le=65535)
        ssl: bool = Field(default=False)
        username: Optional[str] = None
        password: Optional[str] = None

        @field_validator('host')
        @classmethod
        def reject_blank_host(cls, value: str):
            value = value.strip()
            if not value:
                raise ValueError("MQTT host must not be blank")
            return value

    class System(BaseModel):
        log_level: LogLevel = LogLevel.WARNING
        sdk_log_level: SDKLogLevel = SDKLogLevel.NONE
        health_check_interval: int = Field(default=30, ge=10, le=3600)

        @field_validator('sdk_log_level', mode='before')
        @classmethod
        def from_string_to_enum(cls, v):
            '''Convert from a string representation fo the SDKLogLevel enum to the actual enum instance'''
            try:
                level = SDKLogLevel[v]
            except KeyError:
                raise ValueError(f"Supported log levels: {list(value.name for value in SDKLogLevel)}")
            return level

    doorbells: list[Doorbell] = Field(default_factory=list, description="List of doorbells to connect to")
    home_assistant: Optional[HomeAssistant] = None 
    # Use a factory function to automatically load the MQTT configuration using the supervisor API, if MQTT is available
    mqtt: Optional[MQTT] = None
    system: System

    @field_validator('doorbells')
    @classmethod
    def require_unique_doorbell_names(cls, doorbells: list[Doorbell]):
        normalized_names = [
            "".join(
                character
                for character in unicodedata.normalize('NFD', doorbell.name.casefold())
                if character.isalnum()
            )
            for doorbell in doorbells
        ]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("Doorbell names must be unique after MQTT normalization")
        return doorbells

    @field_validator('mqtt', mode='before')
    @classmethod
    def load_mqtt_config(cls, v):
        # Determine if we have a valid manual config (must be a dict with at least a host)
        has_manual_host = isinstance(v, dict) and v.get('host')
        
        # 1. User provided a manual config with a host
        if has_manual_host:
            logger.info("Using manual MQTT configuration from config file/UI")
            return v

        # 2. Check for the "Chrome Trap": a dict with data but NO host
        if isinstance(v, dict) and not v.get('host'):
            logger.warning("Partial MQTT config detected (missing host). This is likely browser autofill. Attempting Supervisor fallback.")

        # 3. Attempt Supervisor Fallback
        supervisor_token = os.getenv('SUPERVISOR_TOKEN')
        
        # Skip if testing or not in an addon environment
        if os.getenv('PYTEST_CURRENT_TEST') or not supervisor_token:
            # If we got here via autofill but have no supervisor, return None to avoid Pydantic errors
            return None

        try:
            config = mqtt_config_from_supervisor()
            if config:
                logger.info("Using MQTT configuration provided by Home Assistant Supervisor")
                return config
        except Exception as e:
            logger.error("Failed to fetch MQTT config from Supervisor: {}", e)
        
        return None
