"""The one run of the tester program in Home Assistant (TESTER-P2, the design's package 2).

A tester takes part ONCE and that one run leaves us everything we need for his boiler (EMS Classic or EMS+, the old
gateway and the Hub alike). The run is a small state machine kept in one record per installation:

    off -> (consent + the recording's own tick) -> recording -> summary -> saved        or: ended (it abandoned itself)

- While it records, the integration reads the Hub once every SAMPLE_S seconds (one sign-in: what the Hub decodes of the
  boiler now, the telegram inventory and the recording's state) and notes which phases it saw (rest, heating, hot
  water). The live evidence list is the rule table (share_format/completeness.json, evaluated by share_format/rules.py,
  the one evaluator) applied to a draft report made from what the Hub reports now; each rule is open, seen or "seen but
  not believable", and ONE sentence says the one thing that helps now. It is evidence driven, not time driven.
- "Finish" stops the recording, reads everything once more, builds the report "boiler-share 2" through the allow-list
  (share_format/fmt.py), validates it with the strict reader and judges it with the same rules. The summary shows
  everything that will be sent, down to the whole file.
- "Save the file" writes the report, the recording, the photo and one zip of the three under
  <config>/emthera_tester/ (never under www: Home Assistant serves www without a sign-in). The files are served
  only by TesterFileView, which needs Home Assistant's sign-in or a signed link that lives LINK_TTL, and they are removed
  after KEEP_FILES_S. Home Assistant sends nothing by itself: the tester sends the file himself, or opens the public form.
- A run nobody finishes ends by itself after ABANDON_S (its photo, its recording state and its files go).

The photo goes in through Home Assistant's own file_upload (the same door the panel's restore uses): share_format/photo.py
writes it again without its hidden data and the original is never kept.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import logging
import re
import zipfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from . import packaged, tester_ot as ot
from .const import DOMAIN
from .share_format import consent as consent_text
from .share_format import auto, fmt, material, photo as photo_mod, rules

_LOGGER = logging.getLogger(__name__)

STORE_KEY = f"{DOMAIN}.tester_run"
STORE_VERSION = 1
BOOK = f"{DOMAIN}_tester_run"
FILES_DIR = "emthera_tester"  # under <config>, NOT under www
FILE_URL = "/api/emthera/tester/file/"

SAMPLE_S = 30                     # one sign-in this often while the run records
ABANDON_S = 24 * 3600             # an unfinished run ends by itself
KEEP_FILES_S = 7 * 86400          # saved files are removed after this
LINK_TTL = timedelta(minutes=5)   # a signed download link lives this long
TEST_MAX_AGE_S = 30 * 86400       # a boiler test older than this is not used
SAVE_DELAY_S = 5
OT_BUSY_RETRY_S = 0.3             # the Hub says "busy" for about 100 ms after a stop: one retry by itself
NOTIFY = "emthera_tester_run_{entry}"

STATES = ("recording", "summary", "saved", "ended")
MARKS = ("heat_up", "hot_water", "restored")
DISPLAY_STATES = ("code", "temperature", "code_and_temperature", "dark", "no_display")
PHASES = ("rest", "heating", "hot_water", "restored")
STEPS = (2, 3, 4, 5, 6, 7, 8)     # the wizard steps a running recording can show (1 and 2-before-start are the page's own; 9 and 10 follow the state)
FIRST_STEP = 3
CODE = re.compile(r"[0-9A-Za-z=+*_./-]{1,3}")
COUNTRY = re.compile(r"[A-Z]{2}")
FILE_NAME = re.compile(r"boiler-share-20[0-9]{2}-[01][0-9]-[0-3][0-9](?:-[0-9]{1,2})?\.(?:json|emsrec\.txt|otrec\.txt|plate\.jpg|zip)")
LINKS = ("ems", "opentherm")      # the kind of Hub this run is for: a bus boiler (EMS) or an OpenTherm boiler
GROUP_EVERY = 4                   # an OpenTherm run reads the numbers per state (eight documents) every 4th sample, and at the end
# Rules the live list does not show: they judge the files, which exist only at the summary.
LIVE_HIDDEN = frozenset({"files_match", "claims_consistent", "consent", "link_known", "software_versions"})
OT_LIVE_HIDDEN = frozenset({"software_versions_ot"})   # the same rule for an OpenTherm Hub
SHOWN_LEVELS = ("send", "read", "tested")
LIVE_READS = ("/boiler/match", "/status/boiler/profile", "/status/ems/devices", "/status/boiler")

TEXT = {
    "en": {
        "ready.hub": "The Hub is connected.", "ready.hub_down": "Home Assistant cannot reach the Hub right now. Check that the Hub is on, then open this page again.",
        "ready.boiler": "The Hub recognised your boiler ({family}).", "ready.boiler_unknown": "The Hub has not recognised your boiler yet. You can still take part: it reads the boiler during the run.",
        "ready.boiler_silent": "The Hub hears no boiler on its cable yet. Check the boiler cable, then open this page again.",
        "ready.thermostat": "Keep your thermostat connected. You do not have to remove or switch off anything for this run.",
        "ready.memory": "The Hub has room for the 30-minute recording.", "ready.memory_no": "This Hub cannot make a recording (no room in its memory). You can still take part, but your report will be incomplete.",
        "ready.memory_old": "This Hub's software cannot make a recording yet. Update the Hub first, or take part without one: your report will then be incomplete.",
        "family.classic": "EMS", "family.plus": "EMS+",
        "next.done": "Everything we need is seen. Choose Finish.", "next.finish_now": "Choose Finish when you are ready.",
        "next.wait": "Nothing to do now. Let the run continue.",
        "next.display": "Tell us what the boiler's display shows now.", "next.photo": "Add a photo of the boiler's type plate (optional to send; needed to count as tested).",
        "next.recording_off": "You chose no recording: the report will be marked incomplete. You can still finish and save it.",
        "test.reused": "The boiler test of {day} is used: {outcome}.", "test.none": "No boiler test is used. Your report can still count as read; to count as tested as well, start the boiler test on the Hub's page.",
        "outcome.passed": "passed", "outcome.failed": "failed", "outcome.stopped": "stopped", "outcome.inconclusive": "not conclusive",
        "outcome.stop_not_supported": "no clean stop", "outcome.attendance_expired": "nobody confirmed it", "outcome.not_started": "not started", "outcome.other": "finished", "outcome.none": "none",
        "head.complete": "Your report is complete.", "head.incomplete": "Your report is not complete yet.",
        "head.tested": "Your report is complete and can count as tested.",
        "ended.abandoned": "The run ended by itself because it was not finished within 24 hours. Nothing was kept. You can start a new run.",
        "line.boiler": "Your boiler as the Hub recognised it: {boiler}.", "line.unknown": "not recognised yet", "line.product": "product {product}", "line.version": "version {version}",
        "line.versions": "The software versions of the Hub ({firmware}) and of this integration ({integration}).",
        "line.telegrams": "Which messages the boiler sends, how often and how long they are ({types} kinds).",
        "line.values": "The values the Hub decoded now: {values}.",
        "line.recording": "The recording of the boiler cable: {minutes} {minutes:minute|minutes} of messages ({frames} messages). It includes room temperatures and the clock of your thermostat.",
        "line.no_recording": "No recording of the boiler cable. The report is marked incomplete.",
        "line.display": "What you told us about the display: {shown}.", "line.country": "Your country: {country}.",
        "line.photo": "One photo of the type plate ({bytes} bytes, without its hidden data).", "line.no_photo": "No photo of the type plate.",
        "line.marks": "The moments you tapped: {marks}.", "line.test": "The boiler test: {outcome}.",
        "line.active": "Active control: {days} days watched; warnings since the takeover: {warnings}.",
        "line.never": "Not in it: your name, address, Wi-Fi name, network addresses, room names, schedules.",
        "mark.heat_up": "thermostat turned up", "mark.hot_water": "hot water tap open", "mark.restored": "all set back",
        "display.code": "a code ({code})", "display.temperature": "a temperature ({temp} degrees)", "display.code_and_temperature": "a code ({code}) and a temperature ({temp} degrees)",
        "display.dark": "nothing (the display is dark)", "display.no_display": "no display on this boiler",
        "form.note": "Everything you post in the public form is public, the recording and the photo included. The form is for people who accept that.",
        "msg.complete.title": "Your boiler report is complete",
        "msg.complete": "The tester run is complete and saved as {name}. Nothing was sent. Download the file in Settings, Installation, Tester program, and send it as you agreed. It stays in Home Assistant for {days} days and can only be opened while you are signed in.",
        "msg.incomplete.title": "Your boiler report is saved, but not complete",
        "msg.incomplete": "The tester run was saved as incomplete ({name}). One thing would complete it: {action} Nothing was sent. It stays in Home Assistant for {days} days and can only be opened while you are signed in.",
        "form.title_unknown": "unknown boiler",
        "msg.ready.title": "Your test recording is long enough: finish your report",
        "msg.ready": "The recording of your boiler cable has run long enough. Open Settings, Installation, Tester program and finish your report. Nothing is sent.",
    },
    "nl": {
        "ready.hub": "De Hub is verbonden.", "ready.hub_down": "Home Assistant bereikt de Hub nu niet. Controleer of de Hub aan staat en open deze pagina dan opnieuw.",
        "ready.boiler": "De Hub heeft je ketel herkend ({family}).", "ready.boiler_unknown": "De Hub heeft je ketel nog niet herkend. Je kunt toch meedoen: hij leest de ketel tijdens de run.",
        "ready.boiler_silent": "De Hub hoort nog geen ketel op zijn kabel. Controleer de ketelkabel en open deze pagina dan opnieuw.",
        "ready.thermostat": "Laat je thermostaat aangesloten. Je hoeft voor deze run niets los te halen of uit te zetten.",
        "ready.memory": "De Hub heeft ruimte voor de opname van 30 minuten.", "ready.memory_no": "Deze Hub kan geen opname maken (geen ruimte in zijn geheugen). Je kunt toch meedoen, maar je melding is dan onvolledig.",
        "ready.memory_old": "De software van deze Hub kan nog geen opname maken. Werk de Hub eerst bij, of doe mee zonder opname: je melding is dan onvolledig.",
        "family.classic": "EMS", "family.plus": "EMS+",
        "next.done": "Alles wat we nodig hebben is gezien. Kies Afronden.", "next.finish_now": "Kies Afronden als je klaar bent.",
        "next.wait": "Nu hoef je niets te doen. Laat de run doorlopen.",
        "next.display": "Vertel ons wat het display van de ketel nu toont.", "next.photo": "Voeg een foto van het typeplaatje van de ketel toe (niet nodig om te versturen; wel om als getest te tellen).",
        "next.recording_off": "Je koos voor geen opname: de melding wordt als onvolledig gemarkeerd. Je kunt hem toch afronden en bewaren.",
        "test.reused": "De keteltest van {day} wordt gebruikt: {outcome}.", "test.none": "Er wordt geen keteltest gebruikt. Je melding kan nog steeds als uitgelezen tellen; om ook als getest te tellen start je de keteltest op de pagina van de Hub.",
        "outcome.passed": "geslaagd", "outcome.failed": "mislukt", "outcome.stopped": "gestopt", "outcome.inconclusive": "niet duidelijk",
        "outcome.stop_not_supported": "geen schone stop", "outcome.attendance_expired": "niemand bevestigde hem", "outcome.not_started": "niet gestart", "outcome.other": "afgelopen", "outcome.none": "geen",
        "head.complete": "Je melding is compleet.", "head.incomplete": "Je melding is nog niet compleet.",
        "head.tested": "Je melding is compleet en kan als getest meetellen.",
        "ended.abandoned": "De run is vanzelf gestopt omdat hij niet binnen 24 uur is afgerond. Er is niets bewaard. Je kunt een nieuwe run starten.",
        "line.boiler": "Je ketel zoals de Hub hem herkent: {boiler}.", "line.unknown": "nog niet herkend", "line.product": "product {product}", "line.version": "versie {version}",
        "line.versions": "De softwareversies van de Hub ({firmware}) en van deze integratie ({integration}).",
        "line.telegrams": "Welke berichten de ketel stuurt, hoe vaak en hoe lang ze zijn ({types} soorten).",
        "line.values": "De waarden die de Hub nu ontcijferde: {values}.",
        "line.recording": "De opname van de ketelkabel: {minutes} {minutes:minuut|minuten} berichten ({frames} berichten). Daarin staan ruimtetemperaturen en de klok van je thermostaat.",
        "line.no_recording": "Geen opname van de ketelkabel. De melding wordt als onvolledig gemarkeerd.",
        "line.display": "Wat je ons over het display vertelde: {shown}.", "line.country": "Je land: {country}.",
        "line.photo": "Eén foto van het typeplaatje ({bytes} bytes, zonder verborgen gegevens).", "line.no_photo": "Geen foto van het typeplaatje.",
        "line.marks": "De momenten die je aantikte: {marks}.", "line.test": "De keteltest: {outcome}.",
        "line.active": "Actieve regeling: {days} dagen gevolgd; waarschuwingen sinds de overname: {warnings}.",
        "line.never": "Er staat niet in: je naam, adres, wifinaam, netwerkadressen, kamernamen, schema's.",
        "mark.heat_up": "thermostaat omhoog", "mark.hot_water": "warmwaterkraan open", "mark.restored": "alles teruggezet",
        "display.code": "een code ({code})", "display.temperature": "een temperatuur ({temp} graden)", "display.code_and_temperature": "een code ({code}) en een temperatuur ({temp} graden)",
        "display.dark": "niets (het display is donker)", "display.no_display": "de ketel heeft geen display",
        "form.note": "Alles wat je in het openbare formulier plaatst is openbaar, ook de opname en de foto. Het formulier is voor wie dat goed vindt.",
        "msg.complete.title": "Je ketelmelding is compleet",
        "msg.complete": "De testerrun is compleet en bewaard als {name}. Er is niets verstuurd. Download het bestand onder Instellen, Installatie, Testerprogramma en stuur het zoals afgesproken. Het blijft {days} dagen in Home Assistant en is alleen te openen als je bent aangemeld.",
        "msg.incomplete.title": "Je ketelmelding is bewaard, maar niet compleet",
        "msg.incomplete": "De testerrun is als onvolledig bewaard ({name}). Eén ding maakt hem compleet: {action} Er is niets verstuurd. Het blijft {days} dagen in Home Assistant en is alleen te openen als je bent aangemeld.",
        "form.title_unknown": "onbekende ketel",
        "msg.ready.title": "Je testopname is lang genoeg: rond je melding af",
        "msg.ready": "De opname van je ketelkabel heeft lang genoeg gelopen. Open Instellen, Installatie, Testerprogramma en rond je melding af. Er wordt niets verstuurd.",
    },
}


def _lang(lang):
    return lang if lang in TEXT else "en"


class _Texts:
    """The sentences of a language: this run's own table, and the OpenTherm lines (tester_ot.TEXT; the Hub's page does not copy them yet).
    A lookup goes to the tables themselves, so nothing is copied."""

    def __init__(self, lang):
        self.own, self.ot = TEXT[lang], ot.TEXT[lang]

    def __getitem__(self, key):
        return self.ot[key] if key in self.ot else self.own[key]

    def __contains__(self, key):
        return key in self.ot or key in self.own

    def get(self, key, default=None):
        return self[key] if key in self else default


def _text(lang):
    return _Texts(_lang(lang))


def _int(v, low=0, high=2 ** 53):
    return v if type(v) is int and low <= v <= high else None


def _dict(v):
    return v if type(v) is dict else {}


def _list(v, limit=64):
    return v[:limit] if type(v) is list else []


# ---- the book: the tester code (once per installation) and the run record of each entry ---------------------------------

def _clean_record(raw):
    """A record as this version writes it, or None (anything else is dropped: a run starts again, nothing breaks)."""
    r = _dict(raw)
    if r.get("state") not in STATES or type(r.get("report_id")) is not str or dt_util.parse_datetime(str(r.get("started"))) is None:
        return None
    display = _dict(r.get("display"))
    out = {
        "state": r["state"], "report_id": r["report_id"], "started": r["started"],
        "consent_version": _int(r.get("consent_version"), 1, 999) or 1,
        "recording_chosen": r.get("recording_chosen") is True, "recording_failed": r.get("recording_failed") in ("unavailable", "not_supported", "failed") and r["recording_failed"] or None,
        "marks": [{"kind": m["kind"], "at_s": m["at_s"]} for m in _list(r.get("marks"), 3)
                  if type(m) is dict and m.get("kind") in MARKS and _int(m.get("at_s"), 0, 7200) is not None],
        "phases": [p for p in _list(r.get("phases"), 4) if p in PHASES],
        "display": {"state": display.get("state") if display.get("state") in DISPLAY_STATES else "not_asked",
                    "code": display.get("code") if type(display.get("code")) is str and CODE.fullmatch(display["code"]) else None,
                    "temp": _int(display.get("temp"), 0, 100)},
        "country": r.get("country") if type(r.get("country")) is str and COUNTRY.fullmatch(r["country"]) else None,
        "photo": None, "saved": None, "ended": r.get("ended") if r.get("ended") in ("abandoned",) else None,
        "step": r.get("step") if type(r.get("step")) is int and r.get("step") in STEPS else FIRST_STEP,
        "notified": r.get("notified") is True, "link": r.get("link") if r.get("link") in LINKS else "ems",
    }
    if out["link"] == "opentherm" and out["recording_failed"] is None:
        out["recording_chosen"] = True      # an OpenTherm run always has its log (no tick): a record from before that says the same
    photo = _dict(r.get("photo"))
    if _int(photo.get("bytes"), 1, photo_mod.MAX_OUTPUT_BYTES) and type(photo.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", photo["sha256"]):
        out["photo"] = {"bytes": photo["bytes"], "sha256": photo["sha256"]}
    saved = _dict(r.get("saved"))
    if saved and dt_util.parse_datetime(str(saved.get("at"))) is not None and type(saved.get("names")) is dict:
        names = {k: v for k, v in saved["names"].items() if k in ("json", "recording", "photo", "zip") and type(v) is str and FILE_NAME.fullmatch(v)}
        if "json" in names:
            out["saved"] = {"at": saved["at"], "complete": saved.get("complete") is True, "names": names,
                            "report": saved.get("report") if type(saved.get("report")) is dict else {}}
    return out


class _Book:
    def __init__(self, hass):
        from homeassistant.helpers.storage import Store
        self.hass = hass
        self.store = Store(hass, STORE_VERSION, STORE_KEY)
        self.data = None
        self.lock = asyncio.Lock()

    def write(self):
        self.store.async_delay_save(lambda: copy.deepcopy(self.data), SAVE_DELAY_S)


async def async_book(hass):
    book = hass.data.get(BOOK)
    if book is None:
        book = hass.data[BOOK] = _Book(hass)
    async with book.lock:
        if book.data is None:
            raw = _dict(await book.store.async_load())
            known = {e.entry_id for e in hass.config_entries.async_entries(DOMAIN)}
            runs = {k: rec for k, v in _dict(raw.get("runs")).items() if k in known and (rec := _clean_record(v)) is not None}
            code = raw.get("tester_code")
            book.data = {"tester_code": code if type(code) is str and re.fullmatch(r"[a-z2-7]{13}", code) else None,
                         "tests": {k: v for k, v in _dict(raw.get("tests")).items() if k in known and type(v) is dict}, "runs": runs}
            if raw and (book.data["runs"] != _dict(raw.get("runs"))):
                book.write()
    return book


# ---- the files: a private folder, never under www -----------------------------------------------------------------------

def files_dir(hass):
    return Path(hass.config.path(FILES_DIR))


def _list_names(folder):
    return {p.name for p in folder.iterdir()} if folder.is_dir() else set()


def pick_names(created, existing, opentherm=False):
    """boiler-share-<date>[-n] .json / .emsrec.txt (.otrec.txt for an OpenTherm boiler) / .plate.jpg / .zip, fresh paths (-2, -3 ... when
    the day's files exist)."""
    base = f"boiler-share-{created}"
    ext = "otrec.txt" if opentherm else "emsrec.txt"
    for n in range(1, 100):
        stem = base if n == 1 else f"{base}-{n}"
        names = {"json": f"{stem}.json", "recording": f"{stem}.{ext}", "photo": f"{stem}.plate.jpg", "zip": f"{stem}.zip"}
        if not set(names.values()) & existing:
            return names
    stem = f"{base}-99"
    return {"json": f"{stem}.json", "recording": f"{stem}.{ext}", "photo": f"{stem}.plate.jpg", "zip": f"{stem}.zip"}


def _write_files(folder, files):
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files:
        (folder / name).write_bytes(data)


def _remove_files(folder, names=None, older_than=None, now=None):
    """Remove named files, or every boiler-share file older than `older_than` seconds. Returns how many are left."""
    left = 0
    if not folder.is_dir():
        return 0
    for path in folder.iterdir():
        if not FILE_NAME.fullmatch(path.name) and not path.name.startswith("pending-"):
            continue
        try:
            if names is not None and path.name in names:
                path.unlink()
            elif older_than is not None and now - path.stat().st_mtime > older_than:
                path.unlink()
            elif names is None and older_than is None:
                path.unlink()
            else:
                left += 1
        except OSError:
            left += 1
    return left


OLD_PUBLIC = re.compile(r"boiler-share-20[0-9]{2}-[01][0-9]-[0-3][0-9](?:-[0-9]{1,2})?\.(?:json|emsrec\.txt)")


def retire_public_files(hass):
    """Up to this version the tester program wrote its files under <config>/www/emthera, which Home Assistant
    serves WITHOUT a sign-in to anyone on the home network. They are removed (once, at an update; nothing else in that
    folder is touched) and the folder with them when it is empty. Runs in the executor. Returns how many files went."""
    folder = Path(hass.config.path("www", "open_thermostat"))
    if not folder.is_dir():
        return 0
    gone = 0
    for path in list(folder.iterdir()):
        if path.is_file() and OLD_PUBLIC.fullmatch(path.name):
            try:
                path.unlink()
                gone += 1
            except OSError:
                pass
    try:
        folder.rmdir()
    except OSError:
        pass
    return gone


def _read_upload(hass, upload_id):
    """The uploaded picture's bytes (at most one byte more than allowed), or None. Runs in the executor; Home Assistant
    removes the upload afterwards: the original is never kept."""
    from homeassistant.components.file_upload import process_uploaded_file
    try:
        with process_uploaded_file(hass, upload_id) as path, path.open("rb") as file:
            return file.read(photo_mod.MAX_INPUT_BYTES + 1)
    except (ValueError, OSError):
        return None


# ---- the report -------------------------------------------------------------------------------------------------------

def _boiler_part(raw):
    from . import boiler_share as share
    match, row, current = share._match(raw.get("/boiler/match"))
    devices = share._devices(raw.get("/status/ems/devices"))
    brand = next((d["brand"] for d in devices if d["bus_address"] == 8), None)
    return match, row, current, brand


def _view(boiler):
    b = _dict(boiler)
    out = {k: _int(b.get(k), -100000, 100000) for k in ("flow_centi_c", "return_centi_c", "modulation_pct", "pressure_deci_bar",
                                                       "heating_limit_c", "dhw_centi_c")}
    code = b.get("display_code")
    out["display_code"] = code.strip() if type(code) is str and CODE.fullmatch(code.strip()) else None
    return out


def _fault(boiler):
    active = _dict(_dict(boiler).get("active_error"))
    code = active.get("code")
    seen = bool(active) and active.get("empty") is not True
    return {"seen": seen, "code": code.strip() if seen and type(code) is str and CODE.fullmatch(code.strip()) else None,
            "class": ("locking" if _dict(boiler).get("lockout") is True else "blocking") if seen else "none"}


def _test_part(family, readiness, plus_probe, match, today, wall, seen_tests, identity, firmware):
    """The boiler test the Hub already keeps (ONE test source: the run never builds its own). Usable only for the same
    boiler and firmware (seen_tests: the moment the test was first seen with this boiler and firmware) and not older than
    30 days; otherwise "no test" (no error)."""
    none = {"kind": "none", "source": "none", "at_day": None, "outcome": "none", "detail": "", "steps": [], "readback": None,
            "reverted": None, "probe": None, "opentherm": None}
    if family == "plus" and type(plus_probe) is dict:
        from . import boiler_share as share
        probe = share._probe(plus_probe)
        last = probe["last"] if probe else None
        if last is None or plus_probe.get("reason") == "other_boiler" or last["age_s"] > TEST_MAX_AGE_S:
            return none
        day = (today - timedelta(seconds=min(last["age_s"], TEST_MAX_AGE_S))).isoformat()
        return {"kind": "plus_probe", "source": "testerprogram", "at_day": day, "outcome": last["outcome"], "detail": last["detail"],
                "steps": [], "readback": probe["readback"], "reverted": last["reverted"], "probe": probe, "opentherm": None}
    if family == "classic":
        test = _dict(_dict(readiness).get("takeover_test"))
        at = test.get("at")
        summary = test.get("summary")
        if type(at) not in (int, float) or at <= 0 or wall - at > TEST_MAX_AGE_S or wall < at:
            return none
        known = _dict(seen_tests)
        if known.get("at") == int(at) and (known.get("boiler") != identity or known.get("firmware") != firmware):
            return none  # another boiler or other firmware since the test was first seen
        outcome = {"passed": "passed", "failed": "failed", "stopped": "stopped", "aborted": "stopped"}.get(summary)
        if outcome is None:
            return none
        steps = _dict(test.get("steps"))
        out = dict(none, kind="ems_takeover", source="testerprogram", outcome=outcome,
                   at_day=dt_util.utc_from_timestamp(at).date().isoformat(),
                   steps=[{"name": name, "ok": steps.get(name) == "pass"} for name in ("disconnect", "confirm", "start", "hot_water", "stop")
                          if name in steps])
        return out
    return none


class RunError(Exception):
    """A refusal the panel explains: the key is a SettingsError key."""

    def __init__(self, key, field=None, **placeholders):
        super().__init__(key)
        self.key, self.field, self.placeholders = key, field, placeholders


class TesterRun:
    """The run of one entry: its record, the live sample, the built report and the files."""

    def __init__(self, hass, entry, link_getter, hub_getter, clock=None, watch_getter=None):
        self.hass, self.entry = hass, entry
        self._link, self._hub, self._watch = link_getter, hub_getter, watch_getter or (lambda: None)
        self._clock = clock or dt_util.utcnow
        self.book = None
        self.record = None
        self.sample = None          # the latest live read: {"boiler", "devices", "recording", "at"}
        self.sample_failed = False
        self.readiness = None       # {"items": [...], "blocking": bool} from the last readiness read
        self.built = None           # the summary's report: {"doc", "result", "names", "files", "text", "collected"}
        self.lock = asyncio.Lock()
        self._load_lock = asyncio.Lock()
        self._loaded = False
        self._unsub = []
        self._sampling = False
        self._ot_samples = 0        # the readings made of an OpenTherm Hub in this run (the numbers per state are read every GROUP_EVERY-th)
        self.via = None             # the way in of the report this run builds: None for a run of a person, "auto" for a report made from the Hub's material (tester_material.py)

    # -- life -----------------------------------------------------------------------------------------------------------

    async def async_load(self):
        """Prepare the format's data (blocking reads, in the executor), load the record and resume what it needs (once)."""
        async with self._load_lock:
            if not self._loaded:
                self._loaded = True
                await self._async_load()

    async def _async_load(self):
        await self.hass.async_add_executor_job(self._prepare)
        self.book = await async_book(self.hass)
        self.record = self.book.data["runs"].get(self.entry.entry_id)
        await self._async_expire_files()
        if self.record is not None and self.record["state"] in ("recording", "summary"):
            if self._abandoned():
                await self._async_end("abandoned")
            elif self.record["state"] == "recording":
                self._start_sampling()
        if self.record is not None and self.record["state"] == "saved":
            self._start_cleaning()

    @staticmethod
    def _prepare():
        from . import boiler_share
        boiler_share.integration_version()
        fmt.allowlist()
        fmt.completeness()
        auto.table()      # the format's other data files, read here once and not in the event loop later
        material.spec()

    @callback
    def stop(self):
        """Stop every timer of the run (the entry unloads, or the program is switched off)."""
        for undo in self._unsub:
            undo()
        self._unsub = []
        self._sampling = False

    async def async_discard(self):
        """The program was switched off (or was, while Home Assistant did not run): the run and its files go."""
        if self.book is None:
            self.book = await async_book(self.hass)
        self.record = self.book.data["runs"].get(self.entry.entry_id)
        await self.async_forget()

    def _is_ot(self):
        """True when this run is the run of a Hub on an OpenTherm boiler."""
        return self.record is not None and self.record["link"] == "opentherm"

    def _holds_recorder(self):
        """True while this run has the Hub's recorder running (a bus recording the tester chose, or the OpenTherm run, which always runs)."""
        record = self.record
        return record is not None and record["state"] == "recording" and (record["recording_chosen"] or (
            record["link"] == "opentherm" and record["recording_failed"] is None))

    async def async_forget(self):
        """The program was switched off: the run, its pending photo and its saved files go."""
        self.stop()
        link = self._link()
        if link is not None and self._holds_recorder():
            await self._async_stop_recording(link)
        self.record, self.built, self.sample, self.readiness = None, None, None, None
        self._sync_issue()
        if self.book is not None and self.book.data["runs"].pop(self.entry.entry_id, None) is not None:
            self.book.write()
        await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass))
        self._clear_message()

    # -- the one Repairs item: a Hub with no room for the recording, while the program is on (a fault of the Hub's memory) ------

    @callback
    def _sync_issue(self):
        from homeassistant.helpers import issue_registry as ir
        issue = f"tester_recording_unavailable_{self.entry.entry_id}"
        wanted = self.record is not None and self.record["state"] in ("recording", "summary") and self.record["recording_failed"] == "unavailable"
        if wanted:
            ir.async_create_issue(self.hass, DOMAIN, issue, is_fixable=False, is_persistent=False, severity=ir.IssueSeverity.WARNING,
                                  translation_key="tester_recording_unavailable", translation_placeholders={"name": self.entry.title})
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue)

    # -- the record -------------------------------------------------------------------------------------------------------

    def _save_record(self):
        self._sync_issue()
        if self.book is None:
            return
        if self.record is None:
            self.book.data["runs"].pop(self.entry.entry_id, None)
        else:
            self.book.data["runs"][self.entry.entry_id] = copy.deepcopy(self.record)
        self.book.write()

    def _started(self):
        return dt_util.parse_datetime(self.record["started"]) if self.record else None

    def _today(self):
        """The local calendar day by the run's own clock: one source of time for the run (file names, the age of a boiler test)."""
        return dt_util.as_local(self._clock()).date()

    def elapsed_s(self):
        started = self._started()
        return max(0, int((self._clock() - started).total_seconds())) if started else 0

    def _abandoned(self):
        return self.record is not None and self.record["state"] in ("recording", "summary") and self.elapsed_s() > ABANDON_S

    async def _async_end(self, reason):
        """The run ended by itself: its sampler, its recording and its pending photo go; the screen says why."""
        self.stop()
        link = self._link()
        if link is not None and self._holds_recorder():
            await self._async_stop_recording(link)
        self.built, self.sample = None, None
        started = self.record["started"]
        self.record = {**self.record, "state": "ended", "ended": reason, "photo": None, "started": started}
        self._save_record()
        self._clear_message()
        await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass), {f"pending-{self.entry.entry_id}.jpg"})

    async def _async_stop_recording(self, link):
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        try:
            await async_e32_call(link, (lambda c: c.async_ot_run(False)) if self._is_ot() else (lambda c: c.async_recording(False)), write=True)
        except ControllerLinkError:
            _LOGGER.debug("Emthera: the recording could not be stopped", exc_info=True)

    # -- reading the Hub --------------------------------------------------------------------------------------------------

    async def async_readiness(self):
        """The readiness check (design step 1): one sign-in. Blocking: the Hub cannot be reached, or no boiler is heard."""
        from .boiler_share import async_status
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        link = self._link()
        items, blocking, status, match_doc, devices_doc, ot_link, ot_run = [], False, None, None, None, None, None
        if link is not None:
            async def read(client):
                out = {"status": await async_status(client)}
                for path in ("/boiler/match", "/status/ems/devices"):
                    try:
                        out[path] = await client.async_tester_read(path)
                    except ControllerLinkError as err:
                        if str(err) != "controller_update_required":
                            raise
                        out[path] = None
                if (_match_of(out["/boiler/match"])[0] or {}).get("family") not in ("classic", "plus"):
                    for path in (ot.OT_LINK, ot.OT_RUN):   # a boiler that is not a bus boiler: is it an OpenTherm one?
                        try:
                            out[path] = await client.async_tester_read(path)
                        except ControllerLinkError as err:
                            if str(err) != "controller_update_required":
                                raise
                            out[path] = None
                return out
            try:
                got = await async_e32_call(link, read, write=False)
                status, match_doc, devices_doc = got["status"], got["/boiler/match"], got["/status/ems/devices"]
                ot_link, ot_run = got.get(ot.OT_LINK), got.get(ot.OT_RUN)
            except ControllerLinkError:
                link = None
        if link is None:
            items.append({"id": "hub", "ok": False, "text": "ready.hub_down"})
            blocking = True
        elif ot.is_link(ot_link):
            items.append({"id": "hub", "ok": True, "text": "ready.hub"})
            more, blocking = ot.readiness(ot_link, ot_run)
            items += more[:1] + [{"id": "thermostat", "ok": True, "text": "ready.ot_thermostat"}] + more[1:]
            items.sort(key=lambda i: ("hub", "boiler", "thermostat", "memory").index(i["id"]))
            self.readiness = {"items": items, "blocking": blocking, "recording_state": "idle", "link": "opentherm"}
            return self.readiness
        else:
            items.append({"id": "hub", "ok": True, "text": "ready.hub"})
            match, _, _ = _match_of(match_doc)
            family = match["family"] if match else "unknown"
            reception = _dict(_dict(_dict(devices_doc).get("boiler")).get("reception")).get("state")
            if family in ("classic", "plus"):
                items.append({"id": "boiler", "ok": True, "text": "ready.boiler", "family": family})
            elif reception in ("no_boiler_reports", "stale") or reception is None and not match:
                items.append({"id": "boiler", "ok": False, "text": "ready.boiler_silent"})
                blocking = True
            else:
                items.append({"id": "boiler", "ok": False, "text": "ready.boiler_unknown"})
        items.append({"id": "thermostat", "ok": True, "text": "ready.thermostat"})
        state = _dict(status).get("state")
        if link is not None:
            items.append({"id": "memory", "ok": state not in ("unavailable", "not_supported"),
                          "text": "ready.memory" if state not in ("unavailable", "not_supported") else
                          "ready.memory_old" if state == "not_supported" else "ready.memory_no", "state": state})
        self.readiness = {"items": items, "blocking": blocking, "recording_state": state, "link": "ems"}
        return self.readiness

    async def async_sample(self, _now=None):
        """One look at the Hub while the run records: phases seen, the telegram counts, the recording's state."""
        from .boiler_share import async_status
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        if self.record is None or self.record["state"] != "recording":
            return
        if self._abandoned():
            async with self.lock:
                if self._abandoned():
                    await self._async_end("abandoned")
            return
        link = self._link()
        if link is None:
            self.sample_failed = True
            return
        if self._is_ot():
            await self._async_sample_ot(link)
            return

        async def read(client):
            out = {"recording": await async_status(client), "/status/version": await client.async_read("/status/version")}
            for path in LIVE_READS:
                try:
                    out[path] = await client.async_tester_read(path)
                except ControllerLinkError as err:
                    if str(err) != "controller_update_required":
                        raise
                    out[path] = None
            return out
        try:
            got = await async_e32_call(link, read, write=False)
        except ControllerLinkError:
            self.sample_failed = True
            return
        self.sample_failed = False
        self.sample = {"raw": {k: v for k, v in got.items() if k != "recording"}, "recording": got["recording"],
                       "at": self._clock().isoformat()}
        self._note_phases(got["/status/boiler"])
        self._note_long_enough()

    async def _async_sample_ot(self, link):
        """One look at an OpenTherm Hub while the run records: its link document and the run's own status; the numbers per state
        (eight documents) every GROUP_EVERY-th time."""
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        count = self._ot_samples
        wanted = count % GROUP_EVERY == 0

        async def read(client):
            out = {"/status/version": await client.async_read("/status/version")}
            for path in (ot.OT_LINK, ot.OT_RUN, ot.OT_TEST):
                out[path] = await self._tolerant(client, path)
            if wanted and ot.run_state(out[ot.OT_RUN]) in ("running", "stopped"):
                out["groups"] = [await self._tolerant(client, ot.group_path(n)) for n in range(ot.GROUPS)]
            return out
        try:
            got = await async_e32_call(link, read, write=False)
        except ControllerLinkError:
            self.sample_failed = True
            return
        self.sample_failed = False
        self._ot_samples = count + 1
        raw = {k: v for k, v in got.items() if k != "groups"}
        raw["groups"] = got["groups"] if "groups" in got else _dict(self.sample).get("raw", {}).get("groups", [])
        self.sample = {"raw": raw, "recording": ot.recording_status(got[ot.OT_RUN]), "at": self._clock().isoformat()}
        self._note_phases_ot(got[ot.OT_RUN])
        self._note_long_enough()

    @staticmethod
    async def _tolerant(client, path):
        """One of the tester's reads; None from firmware that does not have it."""
        from .controller_link import ControllerLinkError
        try:
            return await client.async_tester_read(path)
        except ControllerLinkError as err:
            if str(err) != "controller_update_required":
                raise
            return None

    def _note_phases_ot(self, run_doc):
        """The phases the boiler's own status showed for long enough (the same seconds the rules ask for): rest, heating, hot water."""
        seconds = ot.states_seconds(run_doc)
        if seconds is None or self.record is None:
            return
        seen = set(self.record["phases"]) | {p for p in ot.STATES if seconds[p] >= rules.PHASE_MIN_S[p]}
        phases = [p for p in PHASES if p in seen]
        if phases != self.record["phases"]:
            self.record["phases"] = phases
            self._save_record()

    def _note_long_enough(self):
        """One message when the recording is long enough (waiting brings nothing more): sent once per run, removed when the run ends."""
        record = self.record
        if record is None or record["state"] != "recording" or record["notified"] or not (record["recording_chosen"] or self._is_ot()):
            return
        needed = ot.NEEDED_S if self._is_ot() else fmt.completeness()["rules"]["recording_length"]["params"]["min_s"]
        if (_int(_dict((self.sample or {}).get("recording")).get("seconds")) or 0) < needed:
            return
        from homeassistant.components import persistent_notification
        from .settings import language
        t = _text(language(self.hass, None))
        key = "msg.ready.ot" if self._is_ot() else "msg.ready"
        persistent_notification.async_create(self.hass, t[key], title=t["msg.ready.title"], notification_id=NOTIFY.format(entry=self.entry.entry_id))
        record["notified"] = True
        self._save_record()

    def _note_phases(self, boiler):
        if type(boiler) is not dict or self.record is None:
            return
        heating, hot = boiler.get("heating") is True, boiler.get("hot_water") is True
        seen = set(self.record["phases"])
        if heating:
            seen.add("heating")
        if hot:
            seen.add("hot_water")
        if not heating and not hot and boiler.get("flame") is not True:
            seen.add("rest")
        phases = [p for p in PHASES if p in seen]
        if phases != self.record["phases"]:
            self.record["phases"] = phases
            self._save_record()

    def _start_sampling(self):
        if self._sampling:
            return
        from homeassistant.helpers.event import async_track_time_interval
        self._sampling = True
        self._unsub.append(async_track_time_interval(self.hass, self.async_sample, timedelta(seconds=SAMPLE_S)))
        self.hass.async_create_task(self.async_sample())

    # -- the live evidence --------------------------------------------------------------------------------------------------

    def _raw_live(self):
        raw = dict((self.sample or {}).get("raw") or {})
        raw.setdefault("/boiler/plus-probe", None)
        return raw

    def _live_rec(self):
        """A recording reading made of what the Hub says while the recording still runs: its seconds and the counts of the
        telegram types it counts. The damaged-frame share is only known from the recording itself: None, "not checked"."""
        s = self.sample or {}
        status = _dict(s.get("recording"))
        seconds = min(_int(status.get("seconds")) or 0, 1800)
        types = _dict(_dict(_dict(_dict(s.get("raw")).get("/status/ems/devices")).get("boiler")).get("telegram_inventory"))
        counts = {}
        for e in _list(types.get("types"), 32):
            t = _int(_dict(e).get("type"), 0, 65535)
            if t is not None:
                counts[f"08:{t:#04x}" if t <= 0xFF else f"08:{t:#05x}"] = _int(_dict(e).get("frames")) or 0
        return {"header": {}, "records": 0, "received": _int(status.get("frames")) or 0, "transmitted": 0, "polls": 0,
                "damaged": 0, "malformed": 0, "first_ms": 0, "last_ms": 0, "telegrams": counts, "out_of_order": 0,
                "seconds": seconds, "sha256": "0" * 64, "damaged_ratio": None}

    def live_evidence(self, lang):
        """The evidence list and the one sentence that helps now (None before the first reading)."""
        if self.sample is None or self.record is None:
            return None
        lang = _lang(lang)
        doc = self.draft(live=True)
        try:
            _, results = rules.evaluate(doc, rec=self._live_rec() if self.record["recording_chosen"] else None)
        except (KeyError, TypeError):  # a draft the format cannot hold yet (no reading of the boiler): the list waits
            return None
        table = fmt.completeness()
        items, first_action = [], None
        for r in rules.screen_results(results, doc):
            rule = table["rules"][r["id"]]
            if r["id"] in LIVE_HIDDEN or r["id"] in OT_LIVE_HIDDEN or r["counts_for"] not in SHOWN_LEVELS or r["id"] in ("tested_run_classic", "tested_run_plus", "tested_run_ot", "photo_clean"):
                continue  # the test and the photo have their own steps below the list
            if r["state"] == "not_checked" and r["detail"].get("reason") in ("recording_not_read_yet", "recording_file_not_given"):
                continue  # only the recording itself can answer these: the summary does
            state = "untrusted" if r["state"] == "untrusted" else "seen" if r["state"] == "seen" or rules._skippable(r) else "open"
            word = {"seen": "seen", "open": "missing", "untrusted": "untrusted"}[state]
            text = rules.with_recording_note(rules.rule_text(rule, word, lang, r["detail"], screen=True), r["id"], doc, lang) if state != "seen"                 else rules.rule_text(rule, word, lang, r["detail"], screen=True)
            action = rules.rule_text(rule, "action", lang, r["detail"], screen=True) if state != "seen" else None
            tested = r["counts_for"] == "tested"
            items.append({"id": r["id"], "title": rule["title"][lang], "state": state, "text": text, "action": action, "tested": tested})
            if state != "seen" and first_action is None and not tested:
                first_action = action
        return {"items": items, "next": first_action, "seen": sum(1 for i in items if i["state"] == "seen"), "total": len(items)}

    # -- the draft and the final report ---------------------------------------------------------------------------------

    def _recording_part(self, status, data, names, live):
        from . import boiler_share as share
        chosen = self.record["recording_chosen"]
        extension = "otrec.txt" if self._is_ot() else "emsrec.txt"
        if live and chosen:
            part = share.recording_part(status, file=f"boiler-share-2000-01-01.{extension}", data=b"live", state="ready")
        elif data is not None and chosen:
            part = share.recording_part(status, file=names["recording"], data=data)
        else:
            part = share.recording_part(status, state=self.record["recording_failed"] if self.record["recording_failed"] else None)
        return {**part, "chosen": chosen, "kind": ("otrec 1" if self._is_ot() else "emsrec 1") if part["file"] else None}

    def draft(self, live=False, collected=None, names=None, data=None):
        """The draft report (a plain dict, made only from what the Hub reports and the tester answered), passed through the
        format's allow-list (fmt.project): whatever is not in the list, or does not fit, is not in the result."""
        record = self.record
        if record is None:
            return None
        from . import boiler_share as share
        collected = collected or {}
        raw = collected.get("raw") or self._raw_live()
        match, row, current, brand = _boiler_part(raw)
        family = match["family"] if match else "unknown"
        link = {"classic": "ems_classic", "plus": "ems_plus"}.get(family, "unknown")
        if self._is_ot():
            return self._draft_ot(raw, live, collected, names, data)
        version = _dict(raw.get("/status/version"))
        today = collected.get("today") or self._today()
        boiler = raw.get("/status/boiler")
        devices = share._telegrams(raw.get("/status/ems/devices"))
        boiler_unit = next((d for d in devices["devices"] if d["bus_address"] == 8), None) or {}
        board = "e32v2" if "source" in version else "hub" if version else "unknown"
        status = collected.get("status") or _dict((self.sample or {}).get("recording"))
        file_names = names or pick_names(today.isoformat(), set())
        display = record["display"]
        photo_part = None
        if record["photo"] is not None:
            photo_part = {"file": file_names["photo"], "bytes": record["photo"]["bytes"], "sha256": record["photo"]["sha256"]}
        limit_c = _int(_dict(boiler).get("heating_limit_c"), 20, 95)
        doc = {
            "schema": fmt.SCHEMA, "schema_minor": fmt.allowlist()["minor"], "report_id": record["report_id"],
            "tester_code": (self.book.data["tester_code"] if self.book is not None else None) or "aaaaaaaaaaaaa",
            "created": today.isoformat(), "board": board, "link": link,
            "software": {"firmware": share._text(version.get("version"), share.VERSION),
                         "integration": share._text(share.integration_version(), share.VERSION),
                         "table": match["table"] if match else None, "table_current": current is True},
            "consent": {"text_version": record["consent_version"], "yes": True},
            "run": {"state": "incomplete", "minutes": min(60, self.elapsed_s() // 60), "marks": list(record["marks"]),
                    "phases_seen": list(record["phases"]), "missing": []},
            "human": {"display_state": display["state"], "display_code_typed": display["code"], "display_temp_typed": display["temp"],
                      "country": record["country"], "photo": photo_part},
            "boiler": {"product": match["product"] if match else boiler_unit.get("product"),
                       "version": match["version"] if match else boiler_unit.get("version"),
                       "brand": brand, "family": family if family in ("classic", "plus") else "unknown", "row": row},
            "match": {"state": "unknown" if not match or match["state"] == "not_recognised" else match["state"],
                      "reason": match["reason"] if match else "awaiting_identity",
                      "confirmed": bool(match and match["confirmed"]), "route": match["route"] if match else "none",
                      "capabilities": {k: (match["capabilities"] if match else {}).get(k, "unverified")
                                       for k in ("control", "flow_request", "stop", "dhw_during_heat")}},
            "link_data": {"ems": {
                "fields": share._fields(raw.get("/status/boiler/profile")), "telegrams": devices,
                "settings": {"verified": list(match["settings"]["verified"]) if match else [],
                             "tested": list(match["settings"]["tested"]) if match else []},
                "writes_to_boiler": [],  # only the replay of the recording on the owner's computer can tell
                "limit": {"c": limit_c, "source": "read" if limit_c is not None else "none"},
                "view": _view(boiler), "fault": _fault(boiler)}},
            "test": collected.get("test") or self._test(raw, record_seen=False)[0],
            "recording": self._recording_part(status, data, None if live else file_names, live),
        }
        if collected.get("active_control") is not None:
            doc["active_control"] = collected["active_control"]
        return fmt.project(doc)

    def _draft_ot(self, raw, live, collected, names, data):
        """The draft report of a Hub on an OpenTherm boiler (minor 1): what the Hub's own run recorder and link document say."""
        from . import boiler_share as share
        record = self.record
        today = collected.get("today") or self._today()
        version = _dict(raw.get("/status/version"))
        link_doc, run_doc = raw.get(ot.OT_LINK), raw.get(ot.OT_RUN)
        status = collected.get("status") or _dict((self.sample or {}).get("recording"))
        file_names = names or pick_names(today.isoformat(), set(), opentherm=True)
        display = record["display"]
        photo_part = None
        if record["photo"] is not None:
            photo_part = {"file": file_names["photo"], "bytes": record["photo"]["bytes"], "sha256": record["photo"]["sha256"]}
        doc = {
            "schema": fmt.SCHEMA, "schema_minor": max(1, fmt.allowlist()["minor"]), "report_id": record["report_id"],
            "tester_code": (self.book.data["tester_code"] if self.book is not None else None) or "aaaaaaaaaaaaa",
            "created": today.isoformat(), "board": "hub", "link": "opentherm",
            "software": {"firmware": share._text(version.get("version"), share.VERSION),
                         "integration": share._text(share.integration_version(), share.VERSION), "table": None, "table_current": False},
            "consent": {"text_version": record["consent_version"], "yes": True},
            "run": {"state": "incomplete", "minutes": min(60, self.elapsed_s() // 60), "marks": list(record["marks"]),
                    "phases_seen": list(record["phases"]), "missing": []},
            "human": {"display_state": display["state"], "display_code_typed": display["code"], "display_temp_typed": display["temp"],
                      "country": record["country"], "photo": photo_part},
            "boiler": {"product": None, "version": None, "brand": None, "family": "unknown", "row": None,
                       "opentherm": ot.identity(link_doc, run_doc)},
            "match": {"state": "unknown", "reason": "awaiting_identity", "confirmed": False, "route": "none",
                      "capabilities": {k: "unverified" for k in ("control", "flow_request", "stop", "dhw_during_heat")}},
            "link_data": {"opentherm": ot.link_data(run_doc, raw.get("groups"))},
            "test": collected.get("test") or self._test(raw, record_seen=False)[0],
            "recording": self._recording_part(status, data, None if live else file_names, live),
        }
        if collected.get("active_control") is not None:
            doc["active_control"] = collected["active_control"]
        return fmt.project(doc)

    def _test(self, raw, record_seen):
        """(the test part of the report, the test's own day or None): the boiler test the Hub already keeps (one test source)."""
        if self._is_ot():
            link_doc, test_doc = raw.get(ot.OT_LINK), raw.get(ot.OT_TEST)
            identity = ot.identity(link_doc, None)["digest"]
            firmware = _dict(raw.get("/status/version")).get("version")
            tests = self.book.data["tests"] if self.book is not None else {}
            at = ot.test_seen_key(test_doc)
            seen = tests.get(self.entry.entry_id)
            if record_seen and at is not None and (seen or {}).get("at") != at:
                tests[self.entry.entry_id] = seen = {"at": at, "boiler": identity, "firmware": firmware}
                self.book.write()
            return ot.test_part(test_doc, link_doc, self._today(), self._clock().timestamp(), seen, identity, firmware, TEST_MAX_AGE_S)
        match, _, _, _ = _boiler_part(raw)
        family = match["family"] if match else "unknown"
        hub = self._hub()
        readiness = _dict(_dict(getattr(hub, "status", None)).get("readiness"))
        identity = f"{match['product']}:{match['version']}" if match else None
        firmware = _dict(raw.get("/status/version")).get("version")
        tests = self.book.data["tests"] if self.book is not None else {}
        at = _dict(readiness.get("takeover_test")).get("at")
        seen = tests.get(self.entry.entry_id)
        if record_seen and family == "classic" and type(at) in (int, float) and at > 0 and (seen or {}).get("at") != int(at):
            tests[self.entry.entry_id] = seen = {"at": int(at), "boiler": identity, "firmware": firmware}
            self.book.write()
        test = _test_part(family, readiness, raw.get("/boiler/plus-probe"), match, self._today(), self._clock().timestamp(),
                          seen, identity, firmware)
        return test, test["at_day"]

    async def _async_collect(self):
        """Stop the recording, read everything the report needs, once (one sign-in)."""
        from .boiler_share import active_control_part, async_collect
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        link = self._link()
        if link is None:
            raise RunError("connect_e32")
        if self._is_ot():
            return await self._async_collect_ot(link)

        async def collect(client):
            raw, status, data = await async_collect(client)
            try:
                raw["/status/boiler"] = await client.async_tester_read("/status/boiler")
            except ControllerLinkError as err:
                if str(err) != "controller_update_required":
                    raise
                raw["/status/boiler"] = None
            return raw, status, data
        raw, status, data = await async_e32_call(link, collect, write=True)
        if not self.record["recording_chosen"]:
            data = None  # a recording the tester did not choose (an older one still on the Hub) is never taken
        watch = self._watch()
        log = watch.log.log if watch is not None and watch.log is not None else None
        test, _ = self._test(raw, record_seen=True)
        return {"raw": raw, "status": status, "data": data, "today": self._today(), "test": test,
                "active_control": active_control_part(log, dt_util.utcnow()) if log is not None else None}

    async def _async_collect_ot(self, link):
        """Stop the Hub's run and read everything the report of an OpenTherm boiler needs, once (one sign-in): the link document, the
        run's status, the numbers per state, the boiler test the Hub keeps, and the change log when the tester chose it."""
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call
        chosen = self.record["recording_chosen"]

        async def collect(client):
            raw = {"/status/version": await client.async_read("/status/version")}
            if self.record["recording_failed"] is None:
                try:
                    await client.async_ot_run(False)      # a stop of a stopped run is accepted; a run that is gone is no reason to fail
                except ControllerLinkError as err:
                    if str(err) not in ("controller_ot_no_run", "controller_ot_run_busy"):
                        raise
            for path in (ot.OT_LINK, ot.OT_RUN, ot.OT_TEST):
                raw[path] = await self._tolerant(client, path)
            for _ in range(ot.SETTLE_READS):    # the stop is taken over within a fraction of a second: only a settled run has final numbers and a whole log
                if not ot.unsettled(raw[ot.OT_RUN]):
                    break
                await asyncio.sleep(ot.SETTLE_EVERY_S)
                raw[ot.OT_RUN] = await self._tolerant(client, ot.OT_RUN)
            raw["groups"] = ([await self._tolerant(client, ot.group_path(n)) for n in range(ot.GROUPS)]
                             if ot.run_state(raw[ot.OT_RUN]) in ("running", "stopped") else [])
            status, data = ot.recording_status(raw[ot.OT_RUN]), None
            if chosen and status["state"] == "ready" and status["frames"] > 0:
                try:
                    data = await client.async_ot_run_log()
                except ControllerLinkError as err:
                    _LOGGER.info("Emthera: the change log could not be read (%s)", err)
                if data is not None and len(data) != status["bytes"]:
                    data, status = None, {**status, "state": "failed"}     # the log is not the one the status describes: never taken
                elif data is None:
                    status = {**status, "state": "failed"}
            return raw, status, data
        raw, status, data = await async_e32_call(link, collect, write=True)
        test, _ = self._test(raw, record_seen=True)
        watch = self._watch()
        log = watch.log.log if watch is not None and watch.log is not None else None
        from .boiler_share import active_control_part
        return {"raw": raw, "status": status, "data": data if chosen else None, "today": self._today(), "test": test,
                "active_control": active_control_part(log, dt_util.utcnow()) if log is not None else None}

    def _build(self, collected, names):
        """The report from what was collected: allow-listed, read strictly, judged by the rules.
        Returns (doc, results, levels, problems); no results when the format cannot hold the draft."""
        draft = self.draft(collected=collected, names=names, data=collected["data"])
        problems = fmt.validate(draft)
        if problems:
            return draft, [], {k: False for k in rules.LEVEL_ORDER}, problems
        _, results = rules.evaluate(draft, rec_bytes=collected["data"], photo_bytes=collected.get("photo"))
        if self.via is not None:    # TESTER-AUTO-1: the rules of the way in `auto` (share_format/auto.py); a run of a person is judged as always
            results = auto.adjust(results, draft, self.via, collected["data"])
        levels = auto.levels_of(results, self.via)
        failed = [r["id"] for r in results if r["counts_for"] in ("send", "read") and r["state"] != "seen" and not rules._skippable(r)]
        complete = levels["read"]
        draft["run"] = {**draft["run"], "state": "complete" if complete else "incomplete", "missing": [] if complete else failed[:32]}
        return draft, results, levels, fmt.validate(draft)

    # -- actions ---------------------------------------------------------------------------------------------------------

    def _need_state(self, *states):
        if self.record is None or self.record["state"] not in states:
            raise RunError("tester_run_state")

    async def async_start(self, recording, consent):
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call, failure
        if consent is not True or type(recording) is not bool:
            raise RunError("tester_consent_needed")
        async with self.lock:
            if self.record is not None and self.record["state"] in ("recording", "summary"):
                raise RunError("tester_run_state")
            link = self._link()
            if link is None:
                raise RunError("connect_e32")
            readiness = await self.async_readiness()
            if readiness["blocking"]:
                raise RunError("tester_not_ready")
            failed = None
            opentherm = readiness.get("link") == "opentherm"
            if opentherm:
                failed = await self._async_start_ot(link)
            elif recording:
                try:
                    status = await async_e32_call(link, lambda c: c.async_recording(True), write=True)
                    if type(status) is dict and status.get("state") in ("unavailable", "not_supported", "failed"):
                        failed = status["state"]
                except ControllerLinkError as err:
                    if str(err) == "controller_recording_unavailable":
                        failed = "unavailable"
                    elif str(err) == "controller_update_required":
                        failed = "not_supported"
                    else:
                        key, values = failure(err)
                        raise RunError(key, **values) from None
            book = self.book
            if not book.data["tester_code"]:
                book.data["tester_code"] = fmt.new_tester_code()
            now = self._clock()
            self.record = _clean_record({
                "state": "recording", "report_id": fmt.new_report_id(), "started": now.isoformat(),
                "consent_version": consent_text.version(consent_text.load(packaged.CONSENT_TEXT)), "recording_chosen": (recording or opentherm) and failed is None,   # an OpenTherm run always has its log: no tick
                "recording_failed": failed, "marks": [], "phases": [], "display": {"state": "not_asked"}, "country": None,
                "photo": None, "saved": None, "link": "opentherm" if opentherm else "ems"})
            self.built, self.sample, self._ot_samples = None, None, 0
            self._save_record()
            await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass))
            self._start_sampling()

    async def _async_start_ot(self, link):
        """Start the Hub's own OpenTherm run (it always runs: the numbers are the run). None when it runs; else why not: "unavailable"
        (no room in the Hub's memory: the report is then incomplete). A refusal the tester can act on is a RunError in plain words."""
        from .controller_link import ControllerLinkError
        from .e32_system import async_e32_call, failure
        for attempt in (1, 2):
            try:
                await async_e32_call(link, lambda c: c.async_ot_run(True), write=True)
                return None
            except ControllerLinkError as err:
                code = str(err)
                if code == "controller_ot_run_busy" and attempt == 1:
                    await asyncio.sleep(OT_BUSY_RETRY_S)   # the Hub's engine takes the last request over within about 100 ms
                    continue
                if code == "controller_recording_unavailable":
                    return "unavailable"
                key = {"controller_ot_run_owned": "tester_hub_run_owns", "controller_ot_run_active": "tester_run_elsewhere",
                       "controller_ot_run_busy": "tester_hub_busy", "controller_ot_no_link": "tester_no_link"}.get(code)
                if key is None:
                    key, values = failure(err)
                    raise RunError(key, **values) from None
                raise RunError(key) from None
        return None  # pragma: no cover (the loop returns or raises)

    async def async_mark(self, kind):
        async with self.lock:
            self._need_state("recording")
            if kind not in MARKS:
                raise RunError("tester_input_invalid")
            if any(m["kind"] == kind for m in self.record["marks"]):
                return
            if kind != "restored" and any(m["kind"] == "restored" for m in self.record["marks"]):
                return  # the order is a fact of the run: nothing after "all set back" is an action
            self.record["marks"].append({"kind": kind, "at_s": min(7200, self.elapsed_s())})
            if kind == "restored":
                self.record["phases"] = [p for p in PHASES if p in set(self.record["phases"]) | {"restored"}]
            self._save_record()

    async def async_display(self, state, code=None, temp=None, country=None):
        async with self.lock:
            self._need_state("recording", "summary")
            if state not in DISPLAY_STATES:
                raise RunError("tester_input_invalid", "display_state")
            code = code.strip().upper() if type(code) is str else None
            if state in ("code", "code_and_temperature"):
                if not code or not CODE.fullmatch(code):
                    raise RunError("tester_display_code", "display_code")
            else:
                code = None
            if state in ("temperature", "code_and_temperature"):
                if type(temp) is not int or not 0 <= temp <= 100:
                    raise RunError("tester_display_temp", "display_temp")
            else:
                temp = None
            if country not in (None, "") and not (type(country) is str and COUNTRY.fullmatch(country.upper())):
                raise RunError("tester_input_invalid", "country")
            self.record["display"] = {"state": state, "code": code, "temp": temp}
            self.record["country"] = country.upper() if country else None
            self._save_record()
            self.built = None

    async def async_photo(self, upload_id):
        async with self.lock:
            self._need_state("recording", "summary")
            if type(upload_id) is not str or not upload_id:
                raise RunError("tester_photo_unreadable", "upload_id")
            data = await self.hass.async_add_executor_job(_read_upload, self.hass, upload_id)
            if data is None:
                raise RunError("tester_photo_unreadable", "upload_id")
            try:
                clean = photo_mod.clean(data)
            except photo_mod.PhotoError as err:
                raise RunError("tester_photo_too_large" if err.reason == "too_large" else "tester_photo_unreadable", "upload_id") from None
            del data  # the original is never kept
            path = f"pending-{self.entry.entry_id}.jpg"
            await self.hass.async_add_executor_job(_write_files, files_dir(self.hass), [(path, clean)])
            self.record["photo"] = dict(photo_mod.describe(clean))
            self._save_record()
            self.built = None

    async def async_remove_photo(self):
        async with self.lock:
            self._need_state("recording", "summary")
            self.record["photo"] = None
            self._save_record()
            self.built = None
            await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass), {f"pending-{self.entry.entry_id}.jpg"})

    async def async_finish(self):
        """Stop the recording and build the summary."""
        async with self.lock:
            self._need_state("recording", "summary")
            self.stop()
            collected = await self._async_collect()
            await self._async_attach_photo(collected)
            existing = await self.hass.async_add_executor_job(_list_names, files_dir(self.hass))
            names = pick_names(collected["today"].isoformat(), existing, self._is_ot())
            collected["names"] = names
            self.built = {"collected": collected, "names": names}
            self.record["state"] = "summary"
            self._save_record()
            self._clear_message()

    async def _async_attach_photo(self, collected):
        if self.record["photo"] is None:
            collected["photo"] = None
            return
        path = files_dir(self.hass) / f"pending-{self.entry.entry_id}.jpg"
        data = await self.hass.async_add_executor_job(lambda: path.read_bytes() if path.is_file() else None)
        if data is None or hashlib.sha256(data).hexdigest() != self.record["photo"]["sha256"]:
            self.record["photo"] = None  # the picture is gone: the report says so instead of naming it
            data = None
        collected["photo"] = data

    async def async_restart_run(self):
        """Back to the start (the recording stops; the tester starts over with a new run)."""
        async with self.lock:
            self.stop()
            link = self._link()
            if link is not None and self._holds_recorder():
                await self._async_stop_recording(link)
            if self.record is not None and self.record["state"] == "recording":
                self._clear_message()
            self.record, self.built, self.sample = None, None, None
            self._save_record()
            await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass))

    async def async_step(self, step):
        """The wizard step the tester is at (2 to 8 while the recording runs). Kept with the run, so any device lands on it; never part of the report."""
        async with self.lock:
            self._need_state("recording")
            if type(step) is not int or step not in STEPS:
                raise RunError("tester_input_invalid")
            if self.record["step"] != step:
                self.record["step"] = step
                self._save_record()

    async def async_new_code(self):
        async with self.lock:
            if self.record is not None and self.record["state"] in ("recording", "summary"):
                raise RunError("tester_run_state")
            self.book.data["tester_code"] = fmt.new_tester_code()
            self.book.write()

    async def async_refresh(self, lang="en"):
        """What a screen read needs first: the abandon bound, the summary that must be rebuilt after a restart, the files."""
        async with self.lock:
            if self._abandoned():
                await self._async_end("abandoned")
            if self.record is not None and self.record["state"] == "summary" and self.built is None:
                try:
                    collected = await self._async_collect()
                    await self._async_attach_photo(collected)
                    existing = await self.hass.async_add_executor_job(_list_names, files_dir(self.hass))
                    collected["names"] = pick_names(collected["today"].isoformat(), existing, self._is_ot())
                    self.built = {"collected": collected, "names": collected["names"]}
                except Exception:  # noqa: BLE001 - the screen shows the summary as not readable; the next read tries again
                    _LOGGER.debug("Emthera: the tester summary could not be rebuilt", exc_info=True)
            if self.record is not None and self.record["state"] == "saved":
                await self._async_expire_files()
            if self.record is None:
                await self.async_readiness()

    # -- the summary and the files ---------------------------------------------------------------------------------------

    def summary(self, lang):
        """The summary of design 1.3: complete or not, what is missing, everything that will be sent, the whole file."""
        lang = _lang(lang)
        if self.built is None:
            return None
        t = _text(lang)
        collected = self.built["collected"]
        names = self.built["names"]
        doc, results, levels, problems = self._build(collected, names)
        table = fmt.completeness()
        complete = levels["read"] and not problems
        missing = []
        for r in rules.screen_results(results, doc):
            if r["counts_for"] in ("send", "read") and r["state"] != "seen" and not rules._skippable(r):
                rule = table["rules"][r["id"]]
                text = rules.rule_text(rule, "untrusted" if r["state"] == "untrusted" else "missing", lang, r["detail"], screen=True)
                missing.append({"id": r["id"], "title": rule["title"][lang], "text": rules.with_recording_note(text, r["id"], doc, lang),
                                "action": rules.rule_text(rule, "action", lang, r["detail"], screen=True)})
        recording = doc["recording"]
        data = collected["data"]
        files = [{"kind": "report", "name": names["json"], "bytes": len(fmt.dump(doc))}]
        if data is not None:
            files.append({"kind": "recording", "name": names["recording"], "bytes": len(data)})
        if collected["photo"] is not None:
            files.append({"kind": "photo", "name": names["photo"], "bytes": len(collected["photo"])})
        boiler = doc["boiler"]
        if self._is_ot():
            return self._summary_ot(lang, doc, results, levels, problems, missing, files, data, collected)
        if boiler["product"] is None:
            boiler_text = t["line.unknown"]
        else:
            parts = [t["line.product"].format(product=boiler["product"])]
            if boiler["version"]:
                parts.append(t["line.version"].format(version=boiler["version"]))
            parts.append(t["family." + boiler["family"]] if "family." + boiler["family"] in t else boiler["family"])
            boiler_text = ", ".join(parts)
        view = doc["link_data"]["ems"]["view"]
        values = ", ".join(rules._plain_value(f"{k} {v}", lang) if k != "display_code" else rules._plain_value(f"{k} {v}", lang) for k, v in view.items() if v is not None)
        lines = [t["line.boiler"].format(boiler=boiler_text),
                 t["line.versions"].format(firmware=doc["software"]["firmware"] or "?", integration=doc["software"]["integration"] or "?"),
                 t["line.telegrams"].format(types=len(doc["link_data"]["ems"]["telegrams"]["boiler"]))]
        if values:
            lines.append(t["line.values"].format(values=values))
        if data is not None:
            minutes = max(1, recording["seconds"] // 60) if recording["seconds"] else 0
            lines.append(rules.plural(t["line.recording"], {"minutes": minutes}).format(minutes=minutes,
                                                    frames=f"{recording['frames']:,}".replace(",", "." if lang != "en" else ",")))
        else:
            lines.append(t["line.no_recording"])
        h = doc["human"]
        shown = t["display." + h["display_state"]].format(code=h["display_code_typed"], temp=h["display_temp_typed"]) if h["display_state"] != "not_asked" else None
        if shown:
            lines.append(t["line.display"].format(shown=shown))
        if h["country"]:
            lines.append(t["line.country"].format(country=h["country"]))
        lines.append(t["line.photo"].format(bytes=h["photo"]["bytes"]) if h["photo"] else t["line.no_photo"])
        if doc["run"]["marks"]:
            lines.append(t["line.marks"].format(marks=", ".join(
                f"{t['mark.' + m['kind']]} ({m['at_s'] // 60}:{m['at_s'] % 60:02d})" for m in doc["run"]["marks"])))
        test = doc["test"]
        lines.append(t["line.test"].format(outcome=t.get("outcome." + test["outcome"], t["outcome.other"])))
        if doc.get("active_control"):
            a = doc["active_control"]
            lines.append(t["line.active"].format(days=a["days_active"], warnings=sum(w["count"] for w in a["warnings"].values())))
        lines.append(t["line.never"])
        counts_for = "tested" if levels["tested"] and complete else "read" if complete else "none"
        return {"complete": complete, "counts_for": counts_for,
                "headline": t["head.tested"] if counts_for == "tested" else t["head.complete"] if complete else t["head.incomplete"],
                "missing": missing, "lines": lines, "files": files, "problems": [p["path"] for p in problems],
                "file_text": fmt.dump(doc).decode("utf-8"), "report_id": doc["report_id"], "form_url": self._form_url(doc),
                "form_note": t["form.note"], "recording_chosen": self.record["recording_chosen"],
                "sizes_ok": sum(f["bytes"] for f in files) <= 8 * 1024 * 1024}

    def _summary_ot(self, lang, doc, results, levels, problems, missing, files, data, collected):
        """The summary of a run on an OpenTherm boiler: the same screen, the lines say what the Hub kept of that boiler."""
        t = _text(lang)
        complete = levels["read"] and not problems
        recording = doc["recording"]
        # The Hub's run is gone (a restart took it): the format cannot hold the OpenTherm part. The summary then says what happened and what to do,
        # in the lost sentence and its one action (the Hub's page does the same), and the report is marked incomplete.
        gone = _dict(doc.get("link_data")).get("opentherm") is None
        ot_doc = _dict(_dict(doc.get("link_data")).get("opentherm"))
        ident = _dict(_dict(doc.get("boiler")).get("opentherm"))
        if gone and not missing:
            missing = [{"id": "ot_log", "title": fmt.completeness()["rules"]["ot_log"]["title"][lang], "text": t["lost.ot_run"], "action": t["lost.ot_run.action"]}]
        parts = []
        if ident.get("member") is not None:
            parts.append(t["line.ot_boiler_maker"].format(member=ident["member"]))
        if ident.get("product_type") is not None:
            parts.append(t["line.ot_boiler_type"].format(type=ident["product_type"]))
        if ident.get("product_version") is not None:
            parts.append(t["line.version"].format(version=ident["product_version"]))
        boiler_text = ", ".join(parts + [t["family.opentherm"]]) if parts else t["line.unknown"]
        lines = [t["line.boiler"].format(boiler=boiler_text),
                 t["line.versions"].format(firmware=doc["software"]["firmware"] or "?", integration=doc["software"]["integration"] or "?")]
        names = rules._ot_names([s["id"] for s in ot_doc.get("summary", [])], lang, True)
        if names:
            lines.append(t["line.ot_values"].format(names=names))
        states = ot_doc.get("states")
        if states:
            counts = {k: max(0, states[k] // 60) for k in ot.STATES}
            lines.append(rules.plural(t["line.ot_states"], counts).format(**counts))
        if data is not None:
            minutes = max(1, recording["seconds"] // 60) if recording["seconds"] else 0
            lines.append(rules.plural(t["line.ot_log"], {"minutes": minutes}).format(
                entries=f"{recording['frames']:,}".replace(",", "." if lang != "en" else ","), minutes=minutes))
        else:
            lines.append(t["lost.ot_run"] if gone else t["line.ot_no_log"])
        h = doc["human"]
        shown = t["display." + h["display_state"]].format(code=h["display_code_typed"], temp=h["display_temp_typed"]) if h["display_state"] != "not_asked" else None
        if shown:
            lines.append(t["line.display"].format(shown=shown))
        if h["country"]:
            lines.append(t["line.country"].format(country=h["country"]))
        lines.append(t["line.photo"].format(bytes=h["photo"]["bytes"]) if h["photo"] else t["line.no_photo"])
        if doc["run"]["marks"]:
            lines.append(t["line.marks"].format(marks=", ".join(
                f"{t['mark.' + m['kind']]} ({m['at_s'] // 60}:{m['at_s'] % 60:02d})" for m in doc["run"]["marks"])))
        lines.append(t["line.test"].format(outcome=t.get("outcome." + doc["test"]["outcome"], t["outcome.other"])))
        if doc.get("active_control"):
            a = doc["active_control"]
            lines.append(t["line.active"].format(days=a["days_active"], warnings=sum(w["count"] for w in a["warnings"].values())))
        lines.append(t["line.never"])
        counts_for = "tested" if levels["tested"] and complete else "read" if complete else "none"
        return {"complete": complete, "counts_for": counts_for,
                "headline": t["head.tested"] if counts_for == "tested" else t["head.complete"] if complete else t["head.incomplete"],
                "missing": missing, "lines": lines, "files": files, "problems": [p["path"] for p in problems],
                "file_text": fmt.dump(doc).decode("utf-8"), "report_id": doc["report_id"], "form_url": self._form_url(doc),
                "form_note": t["form.note"], "recording_chosen": self.record["recording_chosen"],
                "sizes_ok": sum(f["bytes"] for f in files) <= 8 * 1024 * 1024}

    @staticmethod
    def _form_url(doc):
        from .boiler_share import ISSUE_FORM, MAX_URL
        b = doc["boiler"]
        key = rules.identity_of(doc)["key"] if doc["link"] == "opentherm" else None
        title = "Boiler profile: " + (f"product {b['product']}" if b["product"] is not None else key if key else "unknown boiler")
        if b["version"]:
            title += f", version {b['version']}"
        short = {"schema": fmt.SCHEMA, "report_id": doc["report_id"], "link": doc["link"], "product": b["product"], "version": b["version"],
                 "state": doc["run"]["state"]}
        url = ISSUE_FORM + "?" + urlencode({"template": "boiler-profile.yml", "title": title, "summary": json.dumps(short, separators=(",", ":"))})
        return url if len(url) <= MAX_URL else ISSUE_FORM + "?" + urlencode({"template": "boiler-profile.yml", "title": title})

    async def async_save(self, lang="en"):
        """Write the files into the private folder, remove the pending photo, tell the tester in one message."""
        async with self.lock:
            self._need_state("summary")
            if self.built is None:
                raise RunError("tester_summary_unreadable")
            collected, names = self.built["collected"], self.built["names"]
            doc, results, levels, problems = self._build(collected, names)
            if problems:
                raise RunError("tester_share_not_written")
            report = fmt.dump(doc)
            files = [(names["json"], report)]
            data, photo = collected["data"], collected["photo"]
            if data is not None:
                files.append((names["recording"], data))
            if photo is not None:
                files.append((names["photo"], photo))
            files.append((names["zip"], _zip(files)))
            try:
                await self.hass.async_add_executor_job(_write_files, files_dir(self.hass), files)
            except OSError:
                raise RunError("tester_share_not_written") from None
            complete = doc["run"]["state"] == "complete"
            saved_names = {"json": names["json"], "zip": names["zip"]}
            if data is not None:
                saved_names["recording"] = names["recording"]
            if photo is not None:
                saved_names["photo"] = names["photo"]
            summary = self.summary(lang)
            self.record = {**self.record, "state": "saved", "photo": None, "saved": {
                "at": self._clock().isoformat(), "complete": complete, "names": saved_names,
                "report": {"report_id": doc["report_id"], "complete": complete,
                           "first_action": (summary["missing"][0]["action"] if summary and summary["missing"] else None)}}}
            self.built = None
            self._save_record()
            await self.hass.async_add_executor_job(_remove_files, files_dir(self.hass), {f"pending-{self.entry.entry_id}.jpg"})
            self._start_cleaning()
            self._message(lang, names["zip"], complete, summary)

    def _message(self, lang, name, complete, summary):
        from homeassistant.components import persistent_notification
        t = _text(lang)
        days = KEEP_FILES_S // 86400
        if complete:
            title, message = t["msg.complete.title"], t["msg.complete"].format(name=name, days=days)
        else:
            action = summary["missing"][0]["action"] if summary and summary["missing"] else ""
            title, message = t["msg.incomplete.title"], t["msg.incomplete"].format(name=name, action=action, days=days)
        persistent_notification.async_create(self.hass, message, title=title, notification_id=NOTIFY.format(entry=self.entry.entry_id))

    def _clear_message(self):
        from homeassistant.components import persistent_notification
        persistent_notification.async_dismiss(self.hass, NOTIFY.format(entry=self.entry.entry_id))

    async def _async_expire_files(self):
        """Saved files older than KEEP_FILES_S are removed; a saved run whose files are gone becomes ended-saved (no links)."""
        folder = files_dir(self.hass)
        now = self._clock().timestamp()
        left = await self.hass.async_add_executor_job(lambda: _remove_files(folder, older_than=KEEP_FILES_S, now=now))
        if self.record is not None and self.record["state"] == "saved" and not left:
            self.record["saved"]["names"] = {}
            self._save_record()

    def _start_cleaning(self):
        if any(True for _ in self._unsub):
            return
        from homeassistant.helpers.event import async_track_time_interval

        async def clean(_now=None):
            await self._async_expire_files()
            if self.record is None or self.record["state"] != "saved" or not self.record["saved"]["names"]:
                self.stop()
        self._unsub.append(async_track_time_interval(self.hass, clean, timedelta(hours=1)))

    def file_links(self):
        """Signed download links for the saved files (they live LINK_TTL); [] when none."""
        if self.record is None or self.record["state"] != "saved":
            return []
        from homeassistant.components.http.auth import async_sign_path
        labels = {"zip": "all", "json": "report", "recording": "recording", "photo": "photo"}
        out = []
        for kind in ("zip", "json", "recording", "photo"):
            name = self.record["saved"]["names"].get(kind)
            if name:
                try:
                    url = async_sign_path(self.hass, FILE_URL + name, LINK_TTL)
                except Exception:  # noqa: BLE001 - no HTTP component (tests): no link, never a broken one
                    url = None
                out.append({"kind": labels[kind], "name": name, "url": url})
        return out

    def days_left(self):
        saved = self.record["saved"] if self.record and self.record["state"] == "saved" else None
        at = dt_util.parse_datetime(saved["at"]) if saved else None
        if at is None:
            return 0
        return max(0, -(-int(KEEP_FILES_S - (self._clock() - at).total_seconds()) // 86400))

    # -- the model the panel shows ---------------------------------------------------------------------------------------

    def model(self, lang):
        """The run as the panel shows it (no Hub request: the sampler keeps the readings)."""
        lang = _lang(lang)
        t = _text(lang)
        record = self.record
        out = {"state": "intro" if record is None else record["state"], "tester_code": (self.book.data["tester_code"] if self.book else None),
               "bounds": {"abandon_h": ABANDON_S // 3600, "keep_days": KEEP_FILES_S // 86400, "link_min": int(LINK_TTL.total_seconds() // 60)}}
        if record is None:
            readiness = self.readiness or {"items": [], "blocking": False, "recording_state": None, "link": "ems"}
            consent = consent_text.text(consent_text.load(packaged.CONSENT_TEXT), lang, readiness.get("link"))
            out["consent"] = {"version": consent_text.version(consent_text.load(packaged.CONSENT_TEXT)), **consent}
            out["link"] = "opentherm" if readiness.get("link") == "opentherm" else "ems"
            out["readiness"] = {"blocking": readiness["blocking"], "items": [
                {"id": i["id"], "ok": i["ok"], "text": t[i["text"]].format(family=t.get("family." + str(i.get("family")), ""))} for i in readiness["items"]]}
            out["recording_available"] = readiness.get("recording_state") not in ("unavailable", "not_supported")
            return out
        out["report_id"] = record["report_id"]
        out["step"] = {"recording": record["step"], "summary": 9, "saved": 10}.get(record["state"])
        out["elapsed_s"] = self.elapsed_s()
        if record["state"] == "recording":
            recording = _dict((self.sample or {}).get("recording"))
            opentherm = record["link"] == "opentherm"   # the Hub's run IS the recording of an OpenTherm boiler: only a Hub without room has none
            out["recording"] = {"chosen": record["recording_chosen"] or (opentherm and record["recording_failed"] is None),
                                "failed": record["recording_failed"], "state": recording.get("state"),
                                "seconds": _int(recording.get("seconds")) or 0, "frames": _int(recording.get("frames")) or 0,
                                "needed_min": (ot.NEEDED_S if opentherm else fmt.completeness()["rules"]["recording_length"]["params"]["min_s"]) // 60}
            out["marks"] = {m["kind"]: m["at_s"] for m in record["marks"]}
            out["phases"] = list(record["phases"])
            out["display"] = dict(record["display"])
            out["country"] = record["country"]
            out["photo"] = dict(record["photo"]) if record["photo"] else None
            out["evidence"] = self.live_evidence(lang)
            out["sample_failed"] = self.sample_failed
            nxt = (out["evidence"] or {}).get("next")
            if nxt is None and out["evidence"] is not None:
                nxt = t["next.done"]
            elif nxt is None:
                nxt = t["next.wait"]
            out["next"] = nxt
            out["abandon_in_h"] = max(0, (ABANDON_S - self.elapsed_s()) // 3600)
            out["test"] = self._test_text(lang)
        elif record["state"] == "summary":
            out["summary"] = self.summary(lang)
            out["display"] = dict(record["display"])
            out["country"] = record["country"]
            out["photo"] = dict(record["photo"]) if record["photo"] else None
            out["abandon_in_h"] = max(0, (ABANDON_S - self.elapsed_s()) // 3600)
        elif record["state"] == "saved":
            saved = record["saved"] or {}
            out["saved"] = {"complete": saved.get("complete") is True, "files": self.file_links(), "days_left": self.days_left(),
                            "first_action": _dict(saved.get("report")).get("first_action"), "form_note": t["form.note"],
                            "report_id": record["report_id"]}
        elif record["state"] == "ended":
            out["ended"] = {"reason": record["ended"], "text": t["ended." + (record["ended"] or "abandoned")]}
        return out

    def _test_text(self, lang):
        t = _text(lang)
        test, day = self._test(self._raw_live(), record_seen=False)
        if test["kind"] == "none":
            return {"state": "none", "text": t["test.none"]}
        return {"state": "reused", "text": t["test.reused"].format(day=day, outcome=t.get("outcome." + test["outcome"], t["outcome.other"]))}


def _match_of(doc):
    from . import boiler_share as share
    return share._match(doc)


def _zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))  # no clock time of the tester's inside the zip
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return buffer.getvalue()


# ---- the download: Home Assistant's sign-in, never the open www folder ------------------------------------------------------

def register_view(hass):
    """/api/emthera/tester/file/<name>: an administrator signed in, or a link signed for LINK_TTL."""
    if hass.data.get(f"{DOMAIN}_tester_view") or getattr(hass, "http", None) is None:
        return
    from aiohttp import web
    from homeassistant.components.http import HomeAssistantView
    from homeassistant.components.http.const import KEY_HASS_USER

    class TesterFileView(HomeAssistantView):
        url = FILE_URL + "{name}"
        name = "api:emthera:tester_file"
        requires_auth = True

        async def get(self, request, name):
            user = request.get(KEY_HASS_USER)
            if user is None or not user.is_admin or not FILE_NAME.fullmatch(name):
                return web.Response(status=404)
            path = files_dir(request.app["hass"]) / name
            data = await request.app["hass"].async_add_executor_job(lambda: path.read_bytes() if path.is_file() else None)
            if data is None:
                return web.Response(status=404)
            kind = "application/zip" if name.endswith(".zip") else "image/jpeg" if name.endswith(".jpg") else "text/plain; charset=utf-8" if name.endswith(".txt") else "application/json"
            return web.Response(body=data, content_type=kind.split(";")[0], charset="utf-8" if "charset" in kind else None,
                                headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store",
                                         "X-Content-Type-Options": "nosniff"})

    hass.http.register_view(TesterFileView())
    hass.data[f"{DOMAIN}_tester_view"] = True
