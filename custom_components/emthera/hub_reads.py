"""Two facts the Hub only tells over its web interface, read when something says they may have changed.

* The names of its Shelly devices and valves (``GET /status/shelly``, e32_devices.remember_names): the Hub is the one
  place where they get their name, and it puts none on MQTT. Read once when the Hub is first heard after Home Assistant
  started and once after every reconnect (it was silent and is heard again, or it restarted), so the room card, the
  Repairs texts and the Batteries list show the Hub's names from the start, not only after the panel was opened.
* Why the takeover ended last (``GET /status``, member ``setup.takeover_ended``, the Hub only; the old gateway never has
  it): read at the same moments and whenever the Hub's active-control state changes, so the reason is there when the
  takeover has just ended and gone when the next confirmation cleared it. It is shown as an attribute of the heat request
  sensor, where the takeover state (``control``) already is: no entity and no Repair of its own.

No timer: the reader is a listener of the hub's own telemetry. A read that fails (the Hub is busy, no free web session)
is tried again with a later telemetry message, at most RETRY_SECONDS apart and MAX_TRIES per cause; firmware without the
route (404) is asked once per reconnect. One sign-in serves both reads. Nothing is written to Home Assistant's registries:
a name the user gave something there is never touched (these names live only in the hub's memory and in attributes).
"""
from __future__ import annotations

import logging

from homeassistant.core import callback

from .controller_link import ControllerLinkError

_LOGGER = logging.getLogger(__name__)

RETRY_SECONDS = 60
MAX_TRIES = 3
REASONS = ("owner", "other_thermostat", "trial_run", "never_reached_guard")

# What each reason says, in the words of the heat request sensor's attribute (and nowhere else).
TAKEOVER_ENDED_TEXT = {
    "en": {
        "owner": "You handed control back, so the Hub does not control the boiler.",
        "other_thermostat": "Another thermostat asked the boiler for heat, so the Hub stopped controlling it. "
                            "Disconnect that thermostat before you confirm the takeover again.",
        "trial_run": "The Hub went back to the trial run: it watches and learns but does not control the boiler "
                     "until you confirm the takeover again.",
        "never_reached_guard": "The Hub's safety check did not accept the confirmation, so the takeover ended "
                               "and the Hub does not control the boiler. Confirm the takeover again.",
    },
    "nl": {
        "owner": "Je hebt de regeling teruggegeven, dus de Hub regelt de ketel niet.",
        "other_thermostat": "Een andere thermostaat vroeg de ketel om warmte, dus de Hub is gestopt met regelen. "
                            "Koppel die thermostaat los voordat je de overname opnieuw bevestigt.",
        "trial_run": "De Hub is teruggegaan naar de proefperiode: hij kijkt en leert, maar regelt de ketel niet "
                     "totdat je de overname opnieuw bevestigt.",
        "never_reached_guard": "De veiligheidscontrole van de Hub accepteerde de bevestiging niet, dus de overname "
                               "is beëindigd en de Hub regelt de ketel niet. Bevestig de overname opnieuw.",
    },
}


def takeover_ended(status):
    """The reason of ``setup.takeover_ended`` in a ``GET /status`` answer, or None (absent, null, unknown word).

    The status line carries the reason word; a document-shaped ``{"reason": ..., "at": ...}`` is read the same way."""
    setup = status.get("setup") if type(status) is dict else None
    value = setup.get("takeover_ended") if type(setup) is dict else None
    if type(value) is dict:
        value = value.get("reason")
    return value if type(value) is str and value in REASONS else None


def takeover_ended_text(reason, lang="en"):
    """The sentence for a reason, in the user's language (English as the last resort); None for no reason."""
    return TAKEOVER_ENDED_TEXT.get(lang, TAKEOVER_ENDED_TEXT["en"]).get(reason)


class HubReads:
    """The reader of one hub; ``start`` hooks it to the hub, the returned function unhooks it."""

    def __init__(self, hass, hub):
        self.hass, self.hub = hass, hub
        self._task = None
        self._running = False    # set before the read starts: a task that finishes at once (eager start) cannot start a second
        self._names_wanted = self._end_wanted = True   # until the Hub is heard and answered once
        self._was_fresh = False
        self._seen = False       # the Hub was heard before: a return after silence is a reconnect
        self._boots = getattr(hub, "boots", 0)
        self._control = None
        self._tries = {"names": 0, "end": 0}
        self._failed_at = None
        self.reads = 0  # sign-ins made (tests)

    @callback
    def start(self):
        remove = self.hub.add_listener(self.changed)
        self.changed()

        @callback
        def stop():
            remove()
            if self._task is not None and not self._task.done():
                self._task.cancel()
        return stop

    @callback
    def changed(self):
        hub = self.hub
        fresh = hub.fresh
        if fresh and not self._was_fresh and self._seen:
            self._reconnected()  # silent, then heard again
        boots = getattr(hub, "boots", 0)
        if boots != self._boots:
            self._boots = boots
            self._reconnected()  # restarted, perhaps on other firmware
        self._was_fresh = fresh
        if fresh:
            self._seen = True
            active = hub.status.get("active") if type(hub.status) is dict else None
            control = active.get("state") if type(active) is dict and type(active.get("state")) is str else None
            if self._control is not None and control != self._control:
                self._end_wanted, self._tries["end"] = True, 0  # the takeover state moved: its reason may have
            self._control = control
        if not fresh or not (self._names_wanted or self._end_wanted):
            return
        plan = hub.plan
        if plan is None or getattr(plan, "login_rejected", False):
            return
        if self._running:
            return
        if self._failed_at is not None and 0 <= hub.clock() - self._failed_at < RETRY_SECONDS:
            return
        self._running = True
        self._task = self.hass.async_create_task(self._read(), "Emthera Hub reads")

    def _reconnected(self):
        self._names_wanted = self._end_wanted = True
        self._tries = {"names": 0, "end": 0}
        self._failed_at = None

    async def _read(self):
        try:
            await self._read_once()
        finally:
            self._running = False

    async def _read_once(self):
        names, end = self._names_wanted, self._end_wanted
        out = {}

        async def read(client):
            if names:
                try:
                    out["names"] = await client.async_shelly_status()
                except ControllerLinkError as err:
                    out["names_error"] = str(err)
            if end:
                try:
                    out["end"] = await client.async_read("/status")
                except ControllerLinkError as err:
                    out["end_error"] = str(err)
        try:
            self.reads += 1
            await self.hub.plan.async_call(read)
        except Exception:  # noqa: BLE001  a background task: nobody retrieves its exception
            _LOGGER.debug("Hub reads failed", exc_info=True)
            self._failed_at = self.hub.clock()
            for key, wanted in (("names", names), ("end", end)):
                if wanted:
                    self._settle(key, "unreachable")
            return
        if names:
            if type(out.get("names")) is dict:
                from .e32_devices import remember_names
                remember_names(self.hub, out["names"])
                self._names_wanted = False
            else:
                self._settle("names", out.get("names_error"))
        if end:
            if type(out.get("end")) is dict:
                reason = takeover_ended(out["end"])
                self._end_wanted = False
                if reason != self.hub.takeover_ended:
                    self.hub.takeover_ended = reason
                    self.hub.notify()
            else:
                self._settle("end", out.get("end_error"))
        if self._names_wanted or self._end_wanted:
            self._failed_at = self.hub.clock()

    def _settle(self, key, error):
        """One read of ``key`` failed: firmware without the route is asked once per reconnect, others a few times."""
        self._tries[key] += 1
        if error == "controller_update_required" or self._tries[key] >= MAX_TRIES:
            if key == "names":
                self._names_wanted = False
            else:
                self._end_wanted = False


@callback
def start_reads(hass, hub):
    """Hook the reader to the hub; returns the function that unhooks it (for ``entry.async_on_unload``)."""
    return HubReads(hass, hub).start()
