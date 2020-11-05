"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.RegisterSystemHealth
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant):
    """Get info for the info page."""

    data = {}
    for entry in hass.data[DOMAIN]:
        for gateway in hass.data[DOMAIN][entry]["gateways"]:
            gateway_name = gateway.gateway.name.replace(" ", "_").lower()
            data[gateway_name] = (
                "Local" if gateway.gateway.local_connection else "Cloud"
            )

    return data
