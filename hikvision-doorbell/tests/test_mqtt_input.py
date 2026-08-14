
import pytest
from pytest_mock import MockerFixture
from config import AppConfig
from doorbell import DeviceType, Doorbell, Registry
from mqtt_input import MQTTInput
from ha_mqtt_discoverable import DeviceInfo
from unittest.mock import Mock


@pytest.fixture
def mock_doorbell(mocker: MockerFixture) -> Doorbell:
    # Create a fake doorbell
    mocked_doorbell = mocker.patch('doorbell.Doorbell')
    mocked_doorbell._type = DeviceType.INDOOR
    mocked_doorbell._config.name = "Test doorbell"
    mocked_doorbell._device_info.serialNumber = lambda: "123"

    return mocked_doorbell


def test_init(mock_doorbell: Doorbell, mocker: MockerFixture):
    registry = Registry()

    registry[0] = mock_doorbell
    
    # Mock call to get DeviceInfo
    extract_device_info = mocker.patch('mqtt_input.extract_device_info', autospec=True)
    dev_info = DeviceInfo(name="test", identifiers="id")
    extract_device_info.return_value = dev_info
    
    # Mock the entities so no MQTT connection is made
    mocker.patch("mqtt_input.Button")
    mocker.patch("mqtt_input.Text")
    mocker.patch("mqtt_input.Image")

    # Fake MQTT settings
    mqtt_config = AppConfig.MQTT(host="localhost")

    input = MQTTInput(mqtt_config, registry)
    assert input is not None


def test_isapi_callback_preserves_payload_spaces(mocker: MockerFixture):
    mqtt_input = MQTTInput.__new__(MQTTInput)
    doorbell = Mock()
    doorbell._config.name = "Entrance"
    doorbell._call_isapi.return_value = "ok"
    text_entity = Mock()
    mqtt_input._sensors = {doorbell: {"isapi_text": text_entity}}
    mqtt_input._get_doorbell_from_args = Mock(return_value=doorbell)
    message = Mock()
    message.payload = (
        b"PUT /ISAPI/example <Root><Value>Hello world</Value></Root>"
    )

    mqtt_input._isapi_input_callback(None, doorbell, message)

    doorbell._call_isapi.assert_called_once_with(
        "PUT",
        "/ISAPI/example",
        "<Root><Value>Hello world</Value></Root>",
    )
    text_entity.set_attributes.assert_called_once_with(
        {"method": "PUT", "path": "/ISAPI/example", "response": "ok"}
    )


def test_isapi_callback_rejects_unsafe_path():
    mqtt_input = MQTTInput.__new__(MQTTInput)
    doorbell = Mock()
    doorbell._config.name = "Entrance"
    text_entity = Mock()
    mqtt_input._sensors = {doorbell: {"isapi_text": text_entity}}
    mqtt_input._get_doorbell_from_args = Mock(return_value=doorbell)
    message = Mock()
    message.payload = b"PUT /System/reboot payload"

    mqtt_input._isapi_input_callback(None, doorbell, message)

    doorbell._call_isapi.assert_not_called()
