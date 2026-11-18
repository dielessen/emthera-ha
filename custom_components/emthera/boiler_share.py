"""The tester program's reads and its evidence of the Hub's own takeover (EMSPLUS-PLAN 3.8, track E5).

The program is switched off by default (Settings -> Installation -> Tester program on the Emthera dashboard; Configure
has the switch too). The run itself, its steps, its live evidence list, the report "boiler-share 2" and the files are
tester_run.py; the format is share_format/ (one implementation, shipped with the integration). This module keeps what
they read and what the Hub does not keep itself:

    GET /status/version, /boiler/match, /status/boiler/profile, /status/ems/devices, /boiler/plus-probe,
    /ems/recording/status, /ems/recording?offset=N     what the Hub already serves (async_collect reads them in one sign-in)

and the filters that fit them to the format's allow-list (_match, _devices, _telegrams, _fields, _probe, recording_part),
and the ActiveControlWatch: while the program is on, Home Assistant follows the heating status it already receives for the
evidence of the Hub's own active control (kept in .storage/emthera.active_control, shared as "active_control").
Nothing is polled or kept while the program is off (switching it off removes that log); no MQTT topic. Home Assistant never
sends anything itself.
"""
from __future__ import annotations

import asyncio
import copy
from functools import lru_cache
import hashlib
import json
import logging
import re
from datetime import timedelta, timezone

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from . import packaged
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_TESTER = "tester_program"
TESTER_ONLY_UPDATE = "tester_only_options"
STATE_KEY = "tester"
# The integration's own, public repository: its issue tracker is the one in manifest.json (the firmware's repository
# is private: a link to it gives a user a 404). The form boiler-profile.yml is published there (scripts/publish_hacs_repo.py).
REPOSITORY = packaged.MANIFEST["issue_tracker"].removesuffix("/issues")
ISSUE_FORM = REPOSITORY + "/issues/new"
MAX_URL = 6 * 1024
WINDOW_S = 1800

OTHER = "other"
PRESENCE = ("supported", "not_fitted", "not_reported", "unknown")
RECEPTION = ("no_boiler_reports", "stale", "conflicting_families", "classic_reports_received", "plus_reports_received")
PLUS_STATES = ("inactive", "shadow", "ready", "active", "stopping", "probe")
PLUS_REASONS = ("verified", "compiled_off", "not_plus", "awaiting_match", "other_boiler", "no_profile", "not_verified",
                "no_proven_stop", "tested_not_reviewed", "not_supported", "foreign_controller", "readback_mismatch")
READBACK = ("none", "pending", "confirmed", "locked_out", "mismatch")
WARNINGS = ("boiler_locked_out", "dhw_hold", "limit_unknown")
PHASES = ("idle", "awaiting_watcher", "reading_limit", "zero", "requesting", "stopping", "reverting")
OUTCOMES = ("passed", "stop_not_supported", "inconclusive", "failed", "not_started", "attendance_expired", "stopped")
DETAILS = ("", "limit_not_read", "limit_too_low", "no_bus_turn", "not_sent", "heating_before_request",
           "readback_mismatch", "boiler_locked_out", "no_flame", "no_heat_response", "flow_too_high",
           "foreign_controller", "route_lost", "pressure_low", "boiler_silent", "clock_changed", "operator_revoked",
           "flame_stayed_on", "setpoint_not_released", "flame_returned", "setpoint_returned", "nobody_confirmed",
           "verified")
RECORDING_STATES = ("idle", "recording", "ready", "unavailable")
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,31}")
BOILER_VERSION = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}")
FIELD = re.compile(r"[a-z][a-z0-9_]{0,47}")
BIG = 2 ** 53

def tester_on(entry):
    return (getattr(entry, "options", None) or {}).get(CONF_TESTER) is True


# ---- the allowlist -------------------------------------------------------------------------------------------------

def _int(v, low=0, high=BIG):
    return v if type(v) is int and low <= v <= high else None


def _word(v, allowed):
    """One of the E32's fixed words; anything else is "other" (a newer firmware), never its text."""
    return v if v in allowed else OTHER


def _text(v, pattern):
    return v if type(v) is str and pattern.fullmatch(v) else None


def _dict(v):
    return v if type(v) is dict else {}


def _list(v, limit):
    return v[:limit] if type(v) is list else []


def _match(doc):
    """The boiler as recognised (GET /boiler/match), through boiler_capabilities.parse (E4's own checks)."""
    from . import boiler_capabilities as caps
    keys = ("schema", "table", "identity", "match", "control", "capabilities", "settings")
    trimmed = {k: doc[k] for k in keys if type(doc) is dict and k in doc}
    if type(trimmed.get("match")) is dict:
        trimmed["match"] = {k: trimmed["match"][k] for k in ("state", "reason", "confirmed", "row_nvs_id")
                            if k in trimmed["match"]}
    parsed = caps.parse(json.dumps(trimmed)) if trimmed else None
    return parsed, (caps.row(parsed)[0] if parsed else None), (caps.table_current(parsed) if parsed else None)


def _devices(doc):
    inventory = _dict(_dict(doc).get("inventory"))
    out = []
    for d in _list(inventory.get("devices"), 16):
        d = _dict(d)
        address = _int(d.get("address"), 1, 255)
        if address is None:
            continue
        out.append({"bus_address": address, "frames": _int(d.get("frames")) or 0,
                    "product": _int(d.get("product_id"), 0, 255), "version": _text(d.get("version"), BOILER_VERSION),
                    "brand": _int(d.get("brand_id"), 0, 255),
                    "types": [t for t in _list(d.get("telegram_types"), 64) if _int(t, 0, 65535) is not None]})
    return out


def _telegrams(doc):
    boiler = _dict(_dict(doc).get("boiler"))
    inventory = _dict(boiler.get("telegram_inventory"))
    reception = _dict(boiler.get("reception"))
    types = []
    for e in _list(inventory.get("types"), 32):
        e = _dict(e)
        t = _int(e.get("type"), 0, 65535)
        if t is None:
            continue
        types.append({"type": t, "frames": _int(e.get("frames")) or 0, "last_offset": _int(e.get("last_offset"), 0, 255) or 0,
                      "last_payload_bytes": _int(e.get("last_payload_bytes"), 0, 255) or 0})
    state = reception.get("state")
    return {"boiler": types, "untracked_frames": _int(inventory.get("untracked_frames")) or 0,
            "reception": None if state is None else _word(state, RECEPTION),
            "report_count": _int(reception.get("report_count")) or 0, "devices": _devices(doc)}


def _fields(doc):
    from .boiler_fields import INDEX_BY_NAME
    out = []
    for f in _list(_dict(doc).get("fields"), 128):
        f = _dict(f)
        index = _int(f.get("index"), 0, 255)
        if index is None:
            continue
        name = _text(f.get("name"), FIELD)
        out.append({"index": index, "name": name if name in INDEX_BY_NAME else None,
                    "state": _word(f.get("state"), PRESENCE), "left_empty": f.get("left_empty") is True})
    return out


def _probe(doc):
    """The EMS+ route and the last attended probe (GET /boiler/plus-probe), without its token or owner."""
    if type(doc) is not dict:
        return None
    probe = _dict(doc.get("probe"))
    foreign = doc.get("foreign")
    out = {"state": _word(doc.get("state"), PLUS_STATES), "reason": _word(doc.get("reason"), PLUS_REASONS),
           "route": _word(doc.get("route"), ("none", "classic_1a", "plus_2e0", "plus_2e0_1a")),
           "refresh_s": _int(doc.get("refresh_s"), 0, 255) or 0,
           **{k: _int(doc.get(k), 0, 255) for k in ("would_c", "thermostat_c", "boiler_c", "limit_c")},
           "readback": _word(doc.get("readback"), READBACK), "mismatches": _int(doc.get("mismatches"), 0, 255) or 0,
           "warnings": [_word(w, WARNINGS) for w in _list(doc.get("warnings"), 8)],
           "foreign": None if type(foreign) is not dict else {"bus_address": _int(foreign.get("address"), 0, 255) or 0,
                                                              "age_s": _int(foreign.get("age_s")) or 0},
           "reads": {"requests": _int(_dict(doc.get("reads")).get("requests")) or 0,
                     "answers": _int(_dict(doc.get("reads")).get("answers")) or 0},
           "phase": _word(probe.get("phase"), PHASES), "last": None}
    last = probe.get("last")
    if type(last) is dict:
        proof = ("unverified", "probe_passed", "verified", "not_supported")
        out["last"] = {
            "outcome": _word(last.get("outcome"), OUTCOMES), "detail": _word(last.get("detail"), DETAILS),
            **{k: _word(last.get(k), proof) for k in ("flow_request", "stop", "dhw_during_heat")},
            **{k: _int(last.get(k), 0, 255) or 0 for k in ("request_c", "limit_c", "minimum_c", "sent")},
            **{k: _int(last.get(k), 0, 65535) for k in ("readback_s", "flame_s", "rise_s", "flame_off_s", "released_s",
                                                        "baseline_centi_c", "peak_centi_c")},
            "last_boiler_c": _int(last.get("last_boiler_c"), 0, 255),
            **{k: last.get(k) is True for k in ("dhw_seen", "dhw_resumed", "reverted")},
            "duration_s": _int(last.get("duration_s")) or 0, "age_s": _int(last.get("age_s")) or 0}
    return out


def recording_part(status, *, file=None, data=None, state=None):
    """The share's "recording": the E32's status (GET /ems/recording/status) and, when written, the file."""
    status = _dict(status)
    chosen = state or _word(status.get("state"), (*RECORDING_STATES, "not_supported", "failed"))
    if chosen == OTHER:
        chosen = "failed"
    return {"state": chosen, "file": file if data is not None else None,
            "bytes": len(data) if data is not None else None,
            "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "seconds": min(_int(status.get("seconds")) or 0, WINDOW_S), "frames": _int(status.get("frames")) or 0,
            "polls": _int(status.get("polls")) or 0, "dropped": _int(status.get("dropped")) or 0}


# ---- active control: the evidence of the E32's own takeover (1.4.2 plan 3.8, review F17/G8) ---------------------
#
# For an EMS Classic boiler the switch-over is the E32's own takeover (TakeoverReadiness, ActiveHeatGuard), and the
# seven days of active control a table row needs are evidence only when nothing went wrong meanwhile. The E32 keeps
# its active-control warnings in RAM only, so while the Tester program is on Home Assistant follows the heating
# status it already receives (no read, no MQTT topic of its own) and keeps, per entry, in
# .storage/emthera.active_control: when the E32 took over, from when Home Assistant watched it, each warning
# kind's count and last moment, how long the status was not seen, and the proof of hot water pausing the E32's heat
# request and the heating resuming. "Share result" adds it as the share's "active_control" part.

WATCHED = ("boiler_no_response", "foreign_controller", "measurement_lost", "transmit_failed")  # = ActiveHeatGuard's
DHW_KINDS = ("tapping", "hot_water", "charging")  # burner.activity: hot water asked (keep_warm is no tap)
WATCH_STORE = f"{DOMAIN}.active_control"
WATCH_STORE_VERSION = 1
WATCH_BOOK = f"{DOMAIN}_active_control"
WATCH_INTERVAL_S = 60
GAP_S = 300            # longer without the E32's heating status counts as not watched
SAVE_EVERY_S = 600     # the "last seen" moment is written at most this often; an evidence change at once
SAVE_DELAY_S = 10
MAX_PAUSE_S = 4 * 3600
MAX_AGE_S = 400 * 86400


def _iso(when):
    return when.isoformat() if when is not None else None


def _when(value):
    when = dt_util.parse_datetime(value) if type(value) is str else None
    return when if when is not None and when.tzinfo is not None else None


def _minute(value):
    when = _when(value)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if when is not None else None


def _new_log(since, now):
    return {"since": _iso(since), "watched_since": _iso(now), "until": None, "seen_at": _iso(now), "unwatched_s": 0,
            "warnings": {kind: {"count": 0, "last_at": None} for kind in WATCHED}, "current": [],
            "dhw_during_heat": None}


def _stored_log(log):
    """A log as this version writes it, or None (anything else starts afresh at the next takeover)."""
    log = _dict(log)
    warnings = _dict(log.get("warnings"))
    dhw = log.get("dhw_during_heat")
    if (_when(log.get("since")) is None or _when(log.get("watched_since")) is None or _when(log.get("seen_at")) is None
            or (log.get("until") is not None and _when(log.get("until")) is None)
            or _int(log.get("unwatched_s")) is None or set(warnings) != set(WATCHED)
            or any(_int(_dict(w).get("count")) is None for w in warnings.values())
            or type(log.get("current")) is not list
            or (dhw is not None and _int(_dict(dhw).get("count"), 1) is None)):
        return None
    return log


class ActiveControlLog:
    """What Home Assistant saw of the E32's active control (pure: the watch and the tests drive it).

    A period starts when the plan is in active mode and the E32 holds the owner's confirmation (it controls the
    boiler). Its "since" is the confirmation's moment when the E32 knows it (confirmed in this E32 run), else the
    first look; the warnings count from "watched_since", the first look. The period ends when the plan leaves active
    mode, and the next takeover starts a new one. A lost confirmation (another controller on the bus, a firmware
    update) does not end it: that is what the warnings record.
    """

    def __init__(self, log=None):
        self.log = _stored_log(log)
        self._pause = None    # (since, kind): hot water interrupted the E32's heat request
        self._heated = False  # the boiler heated on the current heat request

    def observe(self, status, now):
        """One look at the E32's heating status (None while it is not fresh); True when the evidence changed."""
        if type(status) is not dict:
            self._pause, self._heated = None, False
            return False
        mode, active = status.get("mode"), _dict(status.get("active"))
        log, changed = self.log, False
        if log is None or log["until"] is not None:
            confirmation = active.get("confirmation")
            if mode != "active" or type(confirmation) is not dict:
                return False
            age = _int(confirmation.get("age_s"), 0, MAX_AGE_S) if confirmation.get("restored") is False else None
            log = self.log = _new_log(now - timedelta(seconds=age) if age is not None else now, now)
            self._pause, self._heated, changed = None, False, True
        else:
            seen = _when(log["seen_at"])
            gap = int((now - seen).total_seconds()) if seen is not None else 0
            if gap > GAP_S:
                log["unwatched_s"] += gap
                changed = True
            log["seen_at"] = _iso(now)
            if type(mode) is str and mode != "active":
                log["until"], log["current"] = _iso(now), []
                self._pause, self._heated = None, False
                return True
        warnings = active.get("warnings") if mode == "active" else None
        current = [kind for kind in WATCHED if type(warnings) is list and kind in warnings]
        for kind in current:
            if kind not in log["current"]:
                log["warnings"][kind] = {"count": log["warnings"][kind]["count"] + 1, "last_at": _iso(now)}
                changed = True
        if current != log["current"]:
            log["current"], changed = current, True
        return self._hot_water(status, active, now) or changed

    def _hot_water(self, status, active, now):
        """Hot water during the E32's heat request: the boiler heated, made hot water, and heated again."""
        command = _dict(active.get("command"))
        heat = (status.get("mode") == "active" and active.get("state") == "active" and command.get("send") is True
                and _int(command.get("flow_c"), 1, 255) is not None)
        activity = _dict(status.get("burner")).get("activity")
        if not heat:
            self._pause, self._heated = None, False
            return False
        if activity == "heating":
            pause, self._pause, self._heated = self._pause, None, True
            seconds = int((now - pause[0]).total_seconds()) if pause is not None else -1
            if not 0 <= seconds <= MAX_PAUSE_S:
                return False
            count = (self.log["dhw_during_heat"] or {}).get("count", 0)
            self.log["dhw_during_heat"] = {"count": count + 1, "last_at": _iso(now), "last_pause_s": seconds,
                                           "kind": pause[1]}
            return True
        if activity in DHW_KINDS and self._heated and self._pause is None:
            self._pause = (now, activity)
        return False


def active_control_part(log, now):
    """The share's "active_control"; None when Home Assistant never saw the E32 take over while the program was on."""
    log = _stored_log(log)
    if log is None:
        return None
    watched, until = _when(log["watched_since"]), _when(log["until"])
    dhw = log["dhw_during_heat"]
    return {
        "since": _minute(log["since"]), "watched_since": _minute(log["watched_since"]), "until": _minute(log["until"]),
        "days_active": max(0, int(((until or now) - watched).total_seconds()) // 86400),
        "unwatched_min": log["unwatched_s"] // 60,
        "warnings": {kind: {"count": log["warnings"][kind]["count"],
                            "last_at": _minute(_dict(log["warnings"][kind]).get("last_at"))} for kind in WATCHED},
        "dhw_during_heat": None if dhw is None else {
            "count": dhw["count"], "last_at": _minute(dhw.get("last_at")),
            "last_pause_s": _int(dhw.get("last_pause_s"), 0, MAX_PAUSE_S) or 0,
            "kind": dhw.get("kind") if dhw.get("kind") in DHW_KINDS else OTHER},
    }


class _Book:
    """The one store of every entry's log; at load, the logs of entries no longer in Home Assistant go."""

    def __init__(self, hass):
        from homeassistant.helpers.storage import Store
        self.hass = hass
        self.store = Store(hass, WATCH_STORE_VERSION, WATCH_STORE)
        self.data = None
        self.lock = asyncio.Lock()

    def write(self):
        if self.data:
            self.store.async_delay_save(lambda: {"entries": copy.deepcopy(self.data)}, SAVE_DELAY_S)
        else:
            self.hass.async_create_task(self.store.async_remove())


async def async_book(hass):
    """The loaded book (one per Home Assistant)."""
    book = hass.data.get(WATCH_BOOK)
    if book is None:
        book = hass.data[WATCH_BOOK] = _Book(hass)
    async with book.lock:
        if book.data is None:
            raw = _dict(_dict(await book.store.async_load()).get("entries"))
            known = {e.entry_id for e in hass.config_entries.async_entries(DOMAIN)}
            book.data = {k: v for k, v in raw.items() if k in known and _stored_log(v) is not None}
            if raw and book.data != raw:
                book.write()
    return book


async def async_forget_active_control(hass, entry_id):
    """The entry's log goes (the Tester program switched off, or the entry removed)."""
    book = await async_book(hass)
    if book.data.pop(entry_id, None) is not None:
        book.write()


class ActiveControlWatch:
    """While the Tester program is on: each hub change, and once a minute for the gaps, into the entry's log."""

    def __init__(self, hass, entry, hub_getter, clock=None):
        self.hass, self.entry, self._hub = hass, entry, hub_getter
        self._clock = clock or dt_util.utcnow
        self.log = None
        self._book = None
        self._unsub = []
        self._unlisten = None
        self._listening = None
        self._saved_at = None

    @property
    def running(self):
        return bool(self._unsub)

    @callback
    def start(self):
        if self._unsub:
            return
        from homeassistant.helpers.event import async_track_time_interval
        self._unsub.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=WATCH_INTERVAL_S)))
        self.hass.async_create_task(self._async_load())

    async def _async_load(self):
        book = await async_book(self.hass)
        if not self._unsub:
            return
        self._book, self.log, self._saved_at = book, ActiveControlLog(book.data.get(self.entry.entry_id)), None
        self._tick()

    @callback
    def stop(self, forget=False):
        """Stop following; forget: the entry's log goes too (the Tester program switched off)."""
        for undo in self._unsub:
            undo()
        self._unsub = []
        if self._unlisten is not None:
            self._unlisten()
        self._unlisten = self._listening = None
        if forget:
            self.log = None
            self.hass.async_create_task(async_forget_active_control(self.hass, self.entry.entry_id))
        elif self.log is not None and self.log.log is not None:
            self._save(self._clock())

    @callback
    def _tick(self, _now=None):
        hub = self._hub()
        if hub is not self._listening:
            if self._unlisten is not None:
                self._unlisten()
            self._unlisten = hub.add_listener(self.observe) if hub is not None else None
            self._listening = hub
        self.observe()

    @callback
    def observe(self):
        if self.log is None or not self._unsub:
            return
        hub = self._hub()
        now = self._clock()
        changed = self.log.observe(hub.status if hub is not None and hub.fresh else None, now)
        if self.log.log is not None and (changed or self._saved_at is None
                                         or (now - self._saved_at).total_seconds() >= SAVE_EVERY_S):
            self._save(now)

    def _save(self, now):
        if self._book is None:
            return
        self._book.data[self.entry.entry_id] = self.log.log
        self._book.write()
        self._saved_at = now


# ---- E32 requests ---------------------------------------------------------------------------------------------------

READS = ("/boiler/match", "/status/boiler/profile", "/status/ems/devices", "/boiler/plus-probe")


async def async_status(client):
    """The recording's status, or {"state": "not_supported"} on firmware without it."""
    from .controller_link import ControllerLinkError
    try:
        status = await client.async_tester_read("/ems/recording/status")
    except ControllerLinkError as err:
        if str(err) == "controller_update_required":
            return {"state": "not_supported"}
        raise
    return status if type(status) is dict else {"state": "failed"}


async def async_collect(client):
    """Everything "Share result" reads, in the one sign-in of client: (raw, status, recording bytes or None).

    A running recording is stopped first, so it can be downloaded. A read the firmware does not offer is None.
    """
    from .controller_link import ControllerLinkError
    raw = {"/status/version": await client.async_read("/status/version")}
    for path in READS:
        try:
            raw[path] = await client.async_tester_read(path)
        except ControllerLinkError as err:
            if str(err) != "controller_update_required":
                raise
            raw[path] = None
    status = await async_status(client)
    if status.get("state") == "recording":
        status = await client.async_recording(False)
    data = None
    if _dict(status).get("state") == "ready" and _int(status.get("bytes"), 1) is not None:
        try:
            data = await client.async_recording_download(status["bytes"])
        except ControllerLinkError as err:
            _LOGGER.info("Emthera: the bus recording could not be read (%s)", err)
            status = {**status, "state": "failed"}
    return raw, status, data


@lru_cache(maxsize=1)
def integration_version():
    """The integration's version (manifest.json, read once by packaged.py)."""
    return packaged.MANIFEST.get("version")


class TesterMonitor:
    """While the Tester program is on: the active-control watch and the run (tester_run.TesterRun)."""

    def __init__(self, hass, entry, link_getter, hub_getter=None):
        from .tester_run import TesterRun
        self.hass, self.entry, self._link = hass, entry, link_getter
        # The active-control evidence (ActiveControlWatch) while the program is on; None without a hub getter.
        self.watch = ActiveControlWatch(hass, entry, hub_getter) if hub_getter is not None else None
        self.run = TesterRun(hass, entry, link_getter, hub_getter or (lambda: None), watch_getter=lambda: self.watch)

    def start(self):
        """Switched on: load the run (it resumes a recording after a restart); off: nothing of it is kept."""
        from .tester_run import retire_public_files
        self.hass.async_add_executor_job(retire_public_files, self.hass)  # the files of the old version, served without sign-in
        if tester_on(self.entry):
            self.hass.async_create_task(self.run.async_load())
            if self.watch is not None:
                self.watch.start()
        else:
            if self.watch is not None:
                self.watch.stop(forget=True)  # switched off while Home Assistant was not running: its log goes
            self.hass.async_create_task(self._discard())

    async def _discard(self):
        """A run or files left from a program that was switched off meanwhile go (only when there is something)."""
        from .tester_run import async_book, files_dir
        book = await async_book(self.hass)
        if self.entry.entry_id in book.data["runs"] or await self.hass.async_add_executor_job(files_dir(self.hass).is_dir):
            self.run.book = book
            await self.run.async_discard()

    def stop(self, clear=True):
        """clear: the program was switched off (its run, its files and its active-control log go)."""
        self.run.stop()
        if clear:
            if self.watch is not None:
                self.watch.stop(forget=True)
            self.hass.async_create_task(self.run.async_discard())


def save_tester(hass, entry, on):
    """Switch the Tester program on or off (entry options, without a reload); True when it changed."""
    options = {**entry.options, CONF_TESTER: bool(on)}
    if not on:
        options.pop(CONF_TESTER)
    if options == dict(entry.options):
        return False
    state = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if state is not None:
        state[TESTER_ONLY_UPDATE] = dict(options)
    if not hass.config_entries.async_update_entry(entry, options=options) and state is not None:
        state.pop(TESTER_ONLY_UPDATE, None)
    return True


def tester_only_update(state, entry):
    """True (once) when the last options change was the Tester switch alone: the monitor follows, no reload."""
    pending = state.pop(TESTER_ONLY_UPDATE, None) if state is not None else None
    if pending is None or pending != dict(entry.options):
        return False
    monitor = state.get(STATE_KEY)
    if monitor is not None:
        if tester_on(entry):
            monitor.start()
        else:
            monitor.stop()
    return True


def setup_tester(hass, entry, state):
    """The entry's monitor (hass.data[DOMAIN][entry][STATE_KEY]); returns its stop for the entry's cleanup."""
    from .tester_run import register_view
    register_view(hass)
    from .e32_system import link_for
    monitor = TesterMonitor(hass, entry, lambda: link_for(hass, entry), lambda: state.get("heating_hub"))
    state[STATE_KEY] = monitor
    monitor.start()

    def stop():
        monitor.stop(clear=False)
        if monitor.watch is not None:
            monitor.watch.stop()
        state.pop(STATE_KEY, None)
    return stop
