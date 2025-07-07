"""Tests for the devolo Home Network sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    LONG_UPDATE_INTERVAL,
    SHORT_UPDATE_INTERVAL,
    WIFI_APTYPE,
    WIFI_BAND_5G,
    WIFI_BANDS,
    WIFI_VAP_MAIN_AP,
)
from homeassistant.components.sensor import DOMAIN as PLATFORM
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .const import CONNECTED_STATIONS, DISCOVERY_INFO, NO_CONNECTED_STATIONS, PLCNET
from .mock import MockDevice

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test default setup of the sensor component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_connected_wi_fi_clients"
    ).disabled
    assert entity_registry.async_get(
        f"{PLATFORM}.{device_name}_connected_plc_devices"
    ).disabled
    assert entity_registry.async_get(
        f"{PLATFORM}.{device_name}_neighboring_wi_fi_networks"
    ).disabled
    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_plc_downlink_phy_rate_{PLCNET.devices[1].user_device_name}"
    ).disabled
    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_plc_uplink_phy_rate_{PLCNET.devices[1].user_device_name}"
    ).disabled
    assert entity_registry.async_get(
        f"{PLATFORM}.{device_name}_plc_downlink_phy_rate_{PLCNET.devices[2].user_device_name}"
    ).disabled
    assert entity_registry.async_get(
        f"{PLATFORM}.{device_name}_plc_uplink_phy_rate_{PLCNET.devices[2].user_device_name}"
    ).disabled
    assert entity_registry.async_get(
        f"{PLATFORM}.{device_name}_last_restart_of_the_device"
    ).disabled


@pytest.mark.parametrize(
    ("name", "get_method", "interval", "expected_state"),
    [
        (
            "connected_wi_fi_clients",
            "async_get_wifi_connected_station",
            SHORT_UPDATE_INTERVAL,
            "1",
        ),
        (
            "neighboring_wi_fi_networks",
            "async_get_wifi_neighbor_access_points",
            LONG_UPDATE_INTERVAL,
            "1",
        ),
        (
            "connected_plc_devices",
            "async_get_network_overview",
            LONG_UPDATE_INTERVAL,
            "1",
        ),
        (
            "last_restart_of_the_device",
            "async_uptime",
            SHORT_UPDATE_INTERVAL,
            "2023-01-13T11:58:50+00:00",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_sensor(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    name: str,
    get_method: str,
    interval: timedelta,
    expected_state: str,
) -> None:
    """Test state change of a sensor device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{name}"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

    # Emulate device failure
    setattr(mock_device.device, get_method, AsyncMock(side_effect=DeviceUnavailable))
    setattr(mock_device.plcnet, get_method, AsyncMock(side_effect=DeviceUnavailable))
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.reset()
    freezer.tick(interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == expected_state


async def test_update_plc_phyrates(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state change of plc_downlink_phyrate and plc_uplink_phyrate sensor devices."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key_downlink = f"{PLATFORM}.{device_name}_plc_downlink_phy_rate_{PLCNET.devices[1].user_device_name}"
    state_key_uplink = f"{PLATFORM}.{device_name}_plc_uplink_phy_rate_{PLCNET.devices[1].user_device_name}"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key_downlink) == snapshot
    assert entity_registry.async_get(state_key_downlink) == snapshot
    assert hass.states.get(state_key_downlink) == snapshot
    assert entity_registry.async_get(state_key_downlink) == snapshot

    # Emulate device failure
    mock_device.plcnet.async_get_network_overview = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key_downlink)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(state_key_uplink)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Emulate state change
    mock_device.reset()
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key_downlink)
    assert state is not None
    assert state.state == str(PLCNET.data_rates[0].rx_rate)

    state = hass.states.get(state_key_uplink)
    assert state is not None
    assert state.state == str(PLCNET.data_rates[0].tx_rate)


async def test_update_last_update_auth_failed(
    hass: HomeAssistant, mock_device: MockDevice
) -> None:
    """Test getting the last update state with wrong password triggers the reauth flow."""
    entry = configure_integration(hass)
    mock_device.device.async_uptime.side_effect = DevicePasswordProtected

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == entry.entry_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2025-07-07 12:00:00+00:00")
async def test_wifi_device_sensor(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test appearing wifi client."""
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    mac_address = CONNECTED_STATIONS[0].mac_address.replace(":", "_").lower()
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state_key_aptype = f"{PLATFORM}.{mac_address}_network_type"
    state_key_wifi_band = f"{PLATFORM}.{mac_address}_wi_fi_band"

    assert not hass.states.get(state_key_aptype)
    assert not entity_registry.async_get(state_key_aptype)
    assert not hass.states.get(state_key_wifi_band)
    assert not entity_registry.async_get(state_key_wifi_band)

    # Device appears
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=CONNECTED_STATIONS
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(state_key_aptype) == snapshot
    assert entity_registry.async_get(state_key_aptype) == snapshot
    assert hass.states.get(state_key_wifi_band) == snapshot
    assert entity_registry.async_get(state_key_wifi_band) == snapshot

    # Device not home
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state_aptype = hass.states.get(state_key_aptype)
    state_wifi_band = hass.states.get(state_key_wifi_band)
    assert state_aptype is not None
    assert state_aptype.state == STATE_UNKNOWN
    assert state_wifi_band is not None
    assert state_wifi_band.state == STATE_UNKNOWN

    # Emulate device failure
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        side_effect=DeviceUnavailable
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state_aptype = hass.states.get(state_key_aptype)
    state_wifi_band = hass.states.get(state_key_wifi_band)
    assert state_aptype is not None
    assert state_aptype.state == STATE_UNAVAILABLE
    assert state_wifi_band is not None
    assert state_wifi_band.state == STATE_UNAVAILABLE

    # Emulate device recovers
    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=CONNECTED_STATIONS
    )
    freezer.tick(LONG_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state_aptype = hass.states.get(state_key_aptype)
    state_wifi_band = hass.states.get(state_key_wifi_band)
    assert state_aptype is not None
    assert state_aptype.state == WIFI_APTYPE[WIFI_VAP_MAIN_AP]
    assert state_wifi_band is not None
    assert state_wifi_band.state == WIFI_BANDS[WIFI_BAND_5G]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_restoring_clients(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test restoring existing device_tracker entities."""
    mac_address = CONNECTED_STATIONS[0].mac_address
    state_key_aptype = (
        f"{PLATFORM}.{mac_address.replace(':', '_').lower()}_network_type"
    )
    state_key_wifi_band = (
        f"{PLATFORM}.{mac_address.replace(':', '_').lower()}_wi_fi_band"
    )
    entry = configure_integration(hass)
    entity_registry.async_get_or_create(
        PLATFORM,
        DOMAIN,
        f"{DISCOVERY_INFO.properties['SN']}_{mac_address}_network_type",
        config_entry=entry,
    )
    entity_registry.async_get_or_create(
        PLATFORM,
        DOMAIN,
        f"{DISCOVERY_INFO.properties['SN']}_{mac_address}_wi_fi_band",
        config_entry=entry,
    )

    mock_device.device.async_get_wifi_connected_station = AsyncMock(
        return_value=NO_CONNECTED_STATIONS
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state_aptype = hass.states.get(state_key_aptype)
    state_wifi_band = hass.states.get(state_key_wifi_band)
    assert state_aptype is not None
    assert state_aptype.state == STATE_UNKNOWN
    assert state_wifi_band is not None
    assert state_wifi_band.state == STATE_UNKNOWN
