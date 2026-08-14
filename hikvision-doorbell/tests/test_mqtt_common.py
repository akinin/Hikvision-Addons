from ha_mqtt_discoverable import DeviceInfo

from config import AppConfig
from mqtt_common import build_mqtt_settings, entity_unique_id


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
