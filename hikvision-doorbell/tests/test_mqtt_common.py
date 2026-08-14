from unittest.mock import Mock

from ha_mqtt_discoverable import DeviceInfo

from config import AppConfig
from mqtt_common import (
    _managed_entities,
    build_mqtt_settings,
    entity_unique_id,
    manage_mqtt_entity,
    publish_entity_availability,
)


def test_build_mqtt_settings_enables_tls():
    config = AppConfig.MQTT(
        host="mqtt.example.test",
        port=8883,
        ssl=True,
        username="user",
        password="secret",
    )

    settings = build_mqtt_settings(config)

    assert settings.host == "mqtt.example.test"
    assert settings.port == 8883
    assert settings.use_tls is True
    assert settings.username == "user"
    assert settings.password == "secret"


def test_entity_unique_id_uses_hardware_identifier():
    device = DeviceInfo(name="Doorbell", identifiers=["serial-123"])

    assert entity_unique_id(device, "connection") == "serial-123-connection"


def test_publish_availability_bypasses_discoverable_state_cache():
    entity = Mock()
    entity.availability_topic = "hmd/switch/door/availability"
    entity.mqtt_client.publish.return_value.rc = 0

    publish_entity_availability(entity, True)

    entity.mqtt_client.publish.assert_called_once_with(
        "hmd/switch/door/availability", "online", retain=True
    )


def test_managed_entity_restores_discovery_and_availability_on_reconnect():
    _managed_entities.clear()
    entity = Mock()
    entity.config_topic = "homeassistant/switch/door/config"
    entity.availability_topic = "hmd/switch/door/availability"
    entity.mqtt_client.on_connect = None
    entity.mqtt_client.publish.return_value.rc = 0
    reason_code = Mock(is_failure=False)

    manage_mqtt_entity(entity)
    entity.mqtt_client.on_connect(
        entity.mqtt_client, None, {}, reason_code, None
    )

    entity.mqtt_client.reconnect_delay_set.assert_called_once_with(
        min_delay=1, max_delay=30
    )
    entity.write_config.assert_called_once_with()
    entity.mqtt_client.publish.assert_called_once_with(
        "hmd/switch/door/availability", "online", retain=True
    )
