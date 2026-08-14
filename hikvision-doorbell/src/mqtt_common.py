"""Shared helpers for MQTT discovery entities."""

from ha_mqtt_discoverable import DeviceInfo, Settings

from config import AppConfig


def build_mqtt_settings(config: AppConfig.MQTT) -> Settings.MQTT:
    """Translate app MQTT settings to ha-mqtt-discoverable settings."""
    return Settings.MQTT(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        use_tls=config.ssl,
    )


def device_identifier(device: DeviceInfo) -> str:
    """Return the first immutable identifier advertised for a device."""
    identifiers = device.identifiers
    if isinstance(identifiers, list):
        if not identifiers:
            raise ValueError("MQTT device has no identifiers")
        return str(identifiers[0])
    if identifiers is None:
        raise ValueError("MQTT device has no identifier")
    return str(identifiers)


def entity_unique_id(device: DeviceInfo, suffix: str) -> str:
    """Build a stable entity ID from the hardware identifier."""
    return f"{device_identifier(device)}-{suffix}"
