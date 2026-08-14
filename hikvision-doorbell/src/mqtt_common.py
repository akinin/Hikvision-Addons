"""Shared helpers for MQTT discovery entities."""

from typing import Any, Callable

from ha_mqtt_discoverable import DeviceInfo, Discoverable, Settings
from loguru import logger
from paho.mqtt.client import MQTT_ERR_SUCCESS

from config import AppConfig


# Command-only entities used to be referenced only by a setup-local variable.
# Keep them alive so their MQTT network loops cannot be garbage-collected.
_managed_entities: list[Discoverable[Any]] = []


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


def publish_entity_availability(
    entity: Discoverable[Any], available: bool
) -> None:
    """Publish retained availability without the library's state cache.

    The broker publishes an entity's LWT (``offline``) when its connection
    drops.  ha-mqtt-discoverable still remembers its last local value as
    ``online``, so a normal ``set_availability(True)`` can be skipped as an
    unchanged value after reconnect.  A direct retained publish heals that
    mismatch deterministically.
    """
    if not hasattr(entity, "availability_topic"):
        return
    payload = "online" if available else "offline"
    result = entity.mqtt_client.publish(
        entity.availability_topic, payload, retain=True
    )
    if result.rc != MQTT_ERR_SUCCESS:
        logger.warning(
            "Unable to publish MQTT availability for {}: rc={}",
            entity.config_topic,
            result.rc,
        )


def manage_mqtt_entity(entity: Discoverable[Any]) -> Discoverable[Any]:
    """Retain an entity and restore discovery/availability after reconnect."""
    if entity in _managed_entities:
        return entity

    _managed_entities.append(entity)
    client = entity.mqtt_client
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    previous_on_connect: Callable[..., None] | None = client.on_connect

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if previous_on_connect is not None:
            previous_on_connect(
                client, userdata, flags, reason_code, properties
            )
        if getattr(reason_code, "is_failure", False):
            logger.warning(
                "MQTT reconnect failed for {}: {}",
                entity.config_topic,
                reason_code,
            )
            return
        try:
            # Discovery is retained, but rewriting it also repairs a broker
            # restart where retained messages were lost.
            entity.write_config()
            publish_entity_availability(entity, True)
            logger.info("MQTT connection restored for {}", entity.config_topic)
        except Exception as error:
            logger.warning(
                "Failed to restore MQTT entity {}: {}",
                entity.config_topic,
                error,
            )

    client.on_connect = on_connect
    return entity
