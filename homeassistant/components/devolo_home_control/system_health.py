"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass):
    """Get info for the info page."""
    system_health_dict = {}
    for gw in hass.data[DOMAIN]["gateways"]:
        system_health_dict[gw.name] = gw.gateway.local_connection
    return {
        "local_connection": system_health_dict
    }