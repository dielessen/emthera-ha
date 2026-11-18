"""Configure → Advanced and diagnostics → Tester program (track E5, boiler_share.py).

Off by default. The step shows the switch with what the program is in plain words. The run itself (the consent, the 30-minute
recording, the taps, the photo, the summary and the file) lives in the settings panel, Settings → Installation → Tester
program (settings_tester.py, tester_run.py): there is ONE place for it, not two. While the program is on, this step opens a
menu with the one thing Configure still does: "Switch the tester program off", which removes the run and its files.

The one text the menu builds itself is selector.tester_text (EN/NL).
"""
from __future__ import annotations

from .boiler_share import save_tester, tester_on

TEXTS = "tester_text"


class TesterSteps:
    """Mixin for the product options flow."""

    def _tester_link(self):
        from .e32_system import link_for
        return link_for(self.hass, self.config_entry)

    async def async_step_tester(self, user_input=None):
        """The switch while off; the tester's menu while on."""
        import probatio as vol
        from homeassistant.helpers import selector
        if self._tester_link() is None:
            return self.async_abort(reason="e32_rooms_unavailable")
        if tester_on(self.config_entry):
            return await self.async_step_tester_menu()
        if user_input is not None:
            if user_input.get("tester_enabled") is not True:
                return self.async_abort(reason="tester_unchanged")
            save_tester(self.hass, self.config_entry, True)
            texts = await self._tester_texts()
            self._menu_note = texts["switched_on"]
            return await self.async_step_tester_menu()
        return self.async_show_form(step_id="tester", data_schema=vol.Schema({
            vol.Required("tester_enabled", default=False): selector.BooleanSelector()}))

    async def _tester_texts(self):
        from .options_navigation import async_flow_texts
        return await async_flow_texts(self.hass, TEXTS)

    async def async_step_tester_menu(self, user_input=None):
        if self._tester_link() is None:
            return self.async_abort(reason="e32_rooms_unavailable")
        if not tester_on(self.config_entry):
            return await self.async_step_tester()
        return self.async_show_menu(step_id="tester_menu", menu_options=["tester_off"])

    async def async_step_tester_off(self, user_input=None):
        save_tester(self.hass, self.config_entry, False)
        trail = self._trail()
        if trail and trail[-1] == "tester_menu":
            trail.pop()  # the note goes on the menu above it: the tester's own menu is gone
        return self.async_abort(reason="tester_switched_off", description_placeholders={"name": self.config_entry.title})
