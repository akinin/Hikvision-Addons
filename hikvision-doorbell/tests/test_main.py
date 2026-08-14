import asyncio
from unittest.mock import Mock

import pytest

from main import monitor_connections


def test_monitor_reconnects_after_two_failures(mocker):
    doorbell = Mock()
    doorbell._config.name = "Entrance"
    doorbell.get_device_info.side_effect = [RuntimeError("offline"), RuntimeError("offline")]
    mqtt_handler = Mock()
    mqtt_input = Mock()

    sleep = mocker.patch(
        "main.asyncio.sleep",
        side_effect=[None, None, asyncio.CancelledError()],
    )

    async def run_monitor():
        await monitor_connections(
            {0: doorbell},
            mqtt_handler,
            mqtt_input,
            interval=30,
        )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_monitor())

    assert sleep.call_count == 3
    doorbell.disconnect.assert_called_once_with()
    doorbell.authenticate.assert_called_once_with()
    doorbell.setup_alarm.assert_called_once_with()
    mqtt_handler.set_device_availability.assert_any_call(doorbell, False)
    mqtt_handler.set_device_availability.assert_any_call(doorbell, True)
    mqtt_input.set_device_availability.assert_any_call(doorbell, False)
    mqtt_input.set_device_availability.assert_any_call(doorbell, True)
