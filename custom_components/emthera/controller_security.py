"""The Hub's sign-in and https link as the owner sees them (HUB-TLS P3 and P10): the stored pin, and two Repairs issues.

* ``controller_pin_mismatch``: the https peer showed another public key than the one the owner confirmed (a reset of
  the Hub's key, a replaced board, or someone in between). Link features that need the web link stop (the heating
  entities, which run over MQTT, do not). The fix shows the old and the new fingerprint and asks the owner to confirm
  the new one; it probes the Hub again first, so what is stored is what the Hub shows at that moment. Nothing is ever
  accepted silently.
* ``controller_sign_in_downgrade``: an E32 or Hub that offered the safer sign-in (SCRAM) no longer does. Home Assistant
  sends no password to it meanwhile. The fix is for an owner who really put an older firmware back.

Both are faults, not information ("Repairs only for faults"); merely being able to switch an entry to https raises
nothing, and no existing http entry is ever switched by itself.
"""
from __future__ import annotations

import logging

import probatio as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir

from . import controller_pin
from .const import DOMAIN
from .controller_pin import PIN_KEY

PIN_MISMATCH_ISSUE = "controller_pin_mismatch"
DOWNGRADE_ISSUE = "controller_sign_in_downgrade"
# hass.data[DOMAIN][entry id] key: the entry data a pin-only save produced (the update listener then reloads nothing).
PIN_ONLY_UPDATE = "pin_only_data"
_UNSUBSCRIBE = DOMAIN + "_security_listener"
_LOGGER = logging.getLogger(__name__)


def hydrate_pin(entry):
    """Make the entry's confirmed pin known to every client of its address (at set-up); a bad value is ignored."""
    from .controller_link import ControllerLinkError, controller_address
    from .controller_setup_flow import CONTROLLER_ADDRESS
    value = entry.data.get(PIN_KEY)
    if value is None:
        return
    try:
        address = controller_address(entry.data.get(CONTROLLER_ADDRESS))
        controller_pin.register_pin(address, controller_pin.parse_pin(value))
    except (ControllerLinkError, controller_pin.PinError):
        _LOGGER.warning("The stored pin of %s is not usable; connect to its https address again", entry.title)


def with_pin(data, address):
    """``data`` with the pin confirmed for ``address`` (https), or without one (an http address)."""
    result = {k: v for k, v in data.items() if k != PIN_KEY}
    pin = controller_pin.pin_for(address) if address.startswith("https://") else None
    if pin is not None:
        result[PIN_KEY] = controller_pin.pin_text(pin)
    return result


def _entries_at(hass, address):
    from .controller_link import ControllerLinkError, controller_address
    from .controller_setup_flow import CONTROLLER_ADDRESS
    found = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        try:
            if controller_address(entry.data.get(CONTROLLER_ADDRESS)) == address:
                found.append(entry)
        except ControllerLinkError:
            continue
    return found


def _issue_id(kind, entry):
    return f"{kind}_{entry.entry_id}"


@callback
def _on_event(hass, event, address, detail):
    for entry in _entries_at(hass, address):
        if event == "pin_mismatch":
            ir.async_create_issue(
                hass, DOMAIN, _issue_id(PIN_MISMATCH_ISSUE, entry), is_fixable=True, is_persistent=False,
                severity=ir.IssueSeverity.ERROR, translation_key=PIN_MISMATCH_ISSUE,
                translation_placeholders={"name": entry.title},
                data={"entry_id": entry.entry_id,
                      "presented": controller_pin.pin_text(detail) if type(detail) is bytes and len(detail) == 32 else ""})
        elif event == "pin_ok":
            ir.async_delete_issue(hass, DOMAIN, _issue_id(PIN_MISMATCH_ISSUE, entry))
        elif event == "sign_in_downgrade":
            ir.async_create_issue(
                hass, DOMAIN, _issue_id(DOWNGRADE_ISSUE, entry), is_fixable=True, is_persistent=False,
                severity=ir.IssueSeverity.WARNING, translation_key=DOWNGRADE_ISSUE,
                translation_placeholders={"name": entry.title}, data={"entry_id": entry.entry_id})


def register(hass):
    """Listen (once per Home Assistant run) for the pin and sign-in events of the E32 client."""
    from .controller_link import add_security_listener
    previous = hass.data.pop(_UNSUBSCRIBE, None)
    if previous is not None:
        previous()
    hass.data[_UNSUBSCRIBE] = add_security_listener(lambda event, address, detail: _on_event(hass, event, address, detail))


@callback
def save_pin(hass, entry, spki):
    """Store a new pin for the entry's https address: no reload, no plan review (the pin is read when a client opens)."""
    from homeassistant.config_entries import ConfigEntryState
    from .controller_link import controller_address
    from .controller_setup_flow import CONTROLLER_ADDRESS
    controller_pin.register_pin(controller_address(entry.data.get(CONTROLLER_ADDRESS)), spki)
    data = {**entry.data, PIN_KEY: controller_pin.pin_text(spki)}
    state = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry.state is ConfigEntryState.LOADED and state is not None:
        if data == dict(entry.data):
            return
        state[PIN_ONLY_UPDATE] = (data, dict(entry.options))
        if not hass.config_entries.async_update_entry(entry, data=data):
            state.pop(PIN_ONLY_UPDATE, None)
        return
    hass.config_entries.async_update_entry(entry, data=data)


def pin_only_update(state, entry):
    """True (once) when the last entry change was a pin-only save (save_pin)."""
    pending = state.pop(PIN_ONLY_UPDATE, None) if state is not None else None
    return pending is not None and pending == (dict(entry.data), dict(entry.options))


class ConfirmHubIdentityRepairFlow(RepairsFlow):
    """"Confirm the Hub's new identity": shows the old and the new fingerprint; the owner confirms or leaves it.

    The new fingerprint stored is the one the Hub shows when the owner presses confirm (a fresh handshake), not the
    one seen when the issue was raised: when they differ the form is shown again with the newer one.
    """

    def __init__(self, issue_id, data):
        self._issue_id, self._data = issue_id, dict(data) if isinstance(data, dict) else {}

    async def async_step_init(self, user_input=None):
        return await self.async_step_confirm_identity()

    async def async_step_confirm_identity(self, user_input=None):
        from .controller_link import ControllerLinkError, controller_address
        from .controller_setup_flow import CONTROLLER_ADDRESS
        entry = self.hass.config_entries.async_get_entry(self._data.get("entry_id"))
        try:
            address = controller_address(entry.data.get(CONTROLLER_ADDRESS)) if entry is not None else None
        except ControllerLinkError:
            address = None
        if address is None or not address.startswith("https://"):
            return self.async_abort(reason="controller_no_secure_connection")
        old = entry.data.get(PIN_KEY)
        schema = vol.Schema({vol.Required("confirm", default=False): bool})

        def form(errors=None):
            shown = self._data.get("presented") or ""
            try:
                new_text = controller_pin.hex_pairs(controller_pin.parse_pin(shown)) if shown else "-"
                old_text = controller_pin.hex_pairs(controller_pin.parse_pin(old)) if old else "-"
            except controller_pin.PinError:
                new_text = old_text = "-"
            return self.async_show_form(step_id="confirm_identity", data_schema=schema, errors=errors or {},
                                        description_placeholders={"name": entry.title, "old": old_text, "new": new_text})
        if user_input is None:
            return form()
        if user_input.get("confirm") is not True:
            return form({"confirm": "confirm_required"})
        try:
            identity = await controller_pin.async_probe(address)
        except ControllerLinkError:
            return form({"base": "controller_probe_failed"})
        shown = self._data.get("presented") or ""
        if not shown or identity.spki != controller_pin.parse_pin(shown):
            self._data["presented"] = controller_pin.pin_text(identity.spki)  # it moved again: show the newer one
            return form({"base": "identity_changed_again"})
        save_pin(self.hass, entry, identity.spki)
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
        _LOGGER.info("The Hub of %s has a new key; its pin was replaced after the owner's confirmation", entry.title)
        return self.async_create_entry(data={})


class ConfirmSignInDowngradeRepairFlow(RepairsFlow):
    """"Sign-in downgrade": for an owner who really put older firmware back; Home Assistant then uses the old sign-in."""

    def __init__(self, issue_id, data):
        self._issue_id, self._data = issue_id, dict(data) if isinstance(data, dict) else {}

    async def async_step_init(self, user_input=None):
        return await self.async_step_confirm_downgrade()

    async def async_step_confirm_downgrade(self, user_input=None):
        from .controller_link import ControllerLinkError, confirm_sign_in_downgrade, controller_address
        from .controller_setup_flow import CONTROLLER_ADDRESS
        entry = self.hass.config_entries.async_get_entry(self._data.get("entry_id"))
        if entry is None:
            return self.async_abort(reason="controller_no_secure_connection")
        schema = vol.Schema({vol.Required("confirm", default=False): bool})
        if user_input is None:
            return self.async_show_form(step_id="confirm_downgrade", data_schema=schema,
                                        description_placeholders={"name": entry.title})
        if user_input.get("confirm") is not True:
            return self.async_show_form(step_id="confirm_downgrade", data_schema=schema,
                                        errors={"confirm": "confirm_required"},
                                        description_placeholders={"name": entry.title})
        try:
            confirm_sign_in_downgrade(controller_address(entry.data.get(CONTROLLER_ADDRESS)))
        except ControllerLinkError:
            return self.async_abort(reason="controller_no_secure_connection")
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
        return self.async_create_entry(data={})
