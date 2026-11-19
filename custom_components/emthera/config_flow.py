"""Configure OpenThermostat rooms from MQTT discovery or a topic prefix."""

import json

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import CONF_CREATE_DASHBOARD, CONF_TOPIC_PREFIX, DOMAIN
from .v1_config_flow import V1FlowMixin, ShadowOptionsFlow


def valid_prefix(value: str) -> str:
    """Keep a prefix to one MQTT topic level."""
    if not value or "/" in value or "+" in value or "#" in value:
        raise vol.Invalid("Enter a single MQTT topic level")
    return value


class OpenThermostatConfigFlow(V1FlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Add one integration entry per thermostat MQTT prefix."""

    VERSION = 3
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Allow dashboard creation to be changed after setup."""
        from .product import is_product
        if is_product(config_entry):
            from .product_flow import ProductOptionsFlow
            return ProductOptionsFlow()
        return ShadowOptionsFlow()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Adding the integration: an installation of the old name is offered the move first."""
        from . import domain_move
        await domain_move.async_ensure_recovered(self.hass)  # the first code of ours that runs may be this flow
        if domain_move.pending(self.hass) and not getattr(self, "_new_installation", False):
            return await self.async_step_move_choice()
        return await V1FlowMixin.async_step_user(self, user_input)

    async def async_step_move_choice(self, user_input: dict | None = None) -> FlowResult:
        """The menu: move the old installation, or set up a new one (a step of its own: Home Assistant needs a
        method for the step id of every menu and form it shows)."""
        return self.async_show_menu(step_id="move_choice", menu_options=["move_old", "new_installation"])

    async def async_step_new_installation(self, user_input: dict | None = None) -> FlowResult:
        """The user wants a new installation although an old one can be moved."""
        self._new_installation = True
        return await V1FlowMixin.async_step_user(self, user_input)

    async def async_step_move_old(self, user_input: dict | None = None) -> FlowResult:
        """Move the installation of the old name (open_thermostat) to this integration: nothing is lost."""
        from . import domain_move
        if user_input is None:
            names = ", ".join(entry.title for entry in domain_move.old_entries(self.hass))
            return self.async_show_form(step_id="move_old", data_schema=vol.Schema({}),
                                        description_placeholders={"installations": names})
        result = await domain_move.async_move(self.hass, "user")
        if result.status == "moved":
            return self.async_abort(reason="moved_to_emthera")
        if result.status == "nothing":
            return self.async_abort(reason="nothing_to_move")
        if result.reason == "restart":  # the old code is stuck: only a restart of Home Assistant helps
            return self.async_abort(reason="move_restart")
        if result.reason in ("notstarted", "rollback"):  # put back but not started again / the putting back failed too
            return self.async_abort(reason=f"move_{result.reason}")
        if result.reason == "half":  # an earlier move was left halfway: not "nothing was changed, runs as before"
            return self.async_abort(reason="move_half")
        if result.status == "blocked":
            return self.async_abort(reason="move_blocked")
        names = ", ".join(entry.title for entry in domain_move.old_entries(self.hass))
        return self.async_show_form(step_id="move_old", data_schema=vol.Schema({}), errors={"base": "move_failed"},
                                    description_placeholders={"installations": names})

    async def async_step_mqtt(self, discovery_info: MqttServiceInfo) -> FlowResult:
        """Offer setup after a room status message is received."""
        from . import domain_move
        await domain_move.async_ensure_recovered(self.hass)  # the first code of ours that runs may be this discovery
        if discovery_info.topic.endswith("/v1/fw/config/plan"):
            return await self._async_step_announcement()
        try:
            payload = json.loads(discovery_info.payload)
        except (TypeError, ValueError):
            return self.async_abort(reason="invalid_status")
        if not isinstance(payload, dict) or not isinstance(payload.get("rooms"), list):
            return self.async_abort(reason="invalid_status")

        prefix = discovery_info.topic.removesuffix("/room_data")
        try:
            self._prefix = valid_prefix(prefix)
        except vol.Invalid:
            return self.async_abort(reason="invalid_topic")
        await self.async_set_unique_id(self._prefix)
        self._abort_if_unique_id_configured()
        return await self.async_step_confirm()

    async def _async_step_announcement(self) -> FlowResult:
        """A gateway or Hub announced itself (retained, at every start of Home Assistant): the one place of this integration
        that runs before an installation of the new name exists. An installation of the old name is moved, once per run."""
        from . import domain_move
        if domain_move.pending(self.hass) and domain_move.automatic_allowed(self.hass):
            self.hass.async_create_task(domain_move.async_auto_move(self.hass), "emthera move to the new name")
            return self.async_abort(reason="moved_to_emthera")
        return self.async_abort(reason="nothing_to_move")

    async def async_step_confirm(self, user_input: dict | None = None) -> FlowResult:
        """Confirm MQTT discovery."""
        return await self.async_step_installation(user_input)

    async def async_step_legacy(self, user_input: dict | None = None) -> FlowResult:
        """Allow manual setup when MQTT discovery has not appeared yet."""
        errors = {}
        if user_input is not None:
            prefix = user_input[CONF_TOPIC_PREFIX]
            try:
                valid_prefix(prefix)
            except vol.Invalid:
                errors["base"] = "invalid_topic"
            else:
                await self.async_set_unique_id(prefix)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Emthera ({prefix})",
                    data={CONF_TOPIC_PREFIX: prefix},
                    options={CONF_CREATE_DASHBOARD: user_input.get(CONF_CREATE_DASHBOARD, False)},
                )
        return self.async_show_form(
            step_id="legacy",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOPIC_PREFIX, default="ib-therm"): str,
                    vol.Optional(CONF_CREATE_DASHBOARD, default=False): bool,
                }
            ),
            errors=errors,
        )


class OpenThermostatOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure the optional room dashboard."""

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Show the dashboard switch."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_CREATE_DASHBOARD,
                    default=self.config_entry.options.get(CONF_CREATE_DASHBOARD, False),
                ): bool,
            }),
        )
