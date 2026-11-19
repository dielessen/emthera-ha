"""Moving an installation from the integration's old technical name (open_thermostat) to emthera.

Until the rename the integration was called ``open_thermostat`` inside Home Assistant: the config entries, the
registered entities and devices, the repairs and the stored files all belong to that name. A user who updates keeps
all of it. This module moves it, once, and can put it back.

What moves, each kept identical unless the new name forces a change:

* the config entries (same entry id, unique id, data, options, subentries, title): only their domain changes, in place;
* the entity registry rows: same entity id, unique id, name, area, disabled and hidden state; only the platform changes;
* the device registry rows: same devices; their identifiers change from (open_thermostat, x) to (emthera, x);
* the stored files .storage/open_thermostat.* and the tester's folder: COPIED to the new names, read back and compared;
  the old files are never deleted or changed;
* Repairs of the old name: removed from the old name (the running code raises what is still true under the new name).

Before anything changes ONE snapshot is written to .storage/emthera.move_snapshot. A move that fails halfway restores
itself from it (and the snapshot says so); the action emthera.undo_move puts the old names back on request, so that a
user who installs the old version again finds the old installation. A second start after a completed move does
nothing. While the snapshot says "moved", the old action names stay registered as aliases of the new ones and the old
notification event is fired next to the new one (ALIASES_UNTIL says how long).

What starts it: the config flow of this integration (a user who adds Emthera is offered the move first; a Hub or
gateway announcing itself on MQTT starts it once per Home Assistant run), because with the old folder gone nothing
else of ours is loaded before an Emthera entry exists. Situation A (only the new folder exists): the old entries are
there without code. Situation B (both folders exist): the old code started the old entries; the move stops them first.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_TOPIC_PREFIX, DOMAIN, GATEWAY_TOPIC_PREFIX

_LOGGER = logging.getLogger(__name__)

OLD_DOMAIN = "open_thermostat"
SNAPSHOT_KEY = f"{DOMAIN}.move_snapshot"
SNAPSHOT_VERSION = 1
UNDO_SERVICE = "undo_move"
NOTICE_ID = f"{DOMAIN}_moved"
# The old action names and the old notification event stay for this long (the release notes say it, too).
ALIASES_UNTIL = "the whole 1.x line of releases; they are removed only in a later major release, announced one release before"
OLD_EVENT = "open_thermostat_notification"
UNLOAD_LIMIT = 180  # seconds for stopping (or starting again) all entries of one side together; then the move gives up
HOMEASSISTANT_DOMAIN = "homeassistant"

IN_PROGRESS, MOVED, FAILED, UNDONE = "in_progress", "moved", "failed", "undone"
STEPS = ("stop", "snapshot", "files", "base", "devices", "entities", "entries", "issues", "commit")

_LOCK = f"{DOMAIN}_move_lock"
_ATTEMPTED = f"{DOMAIN}_move_attempted"
_ALIASES = f"{DOMAIN}_move_aliases"
_RECOVERED = f"{DOMAIN}_move_recovered"
_inject: tuple[str, int] | None = None  # tests only: raise before item N of a step (N = items done so far)


class MoveFailure(Exception):
    """A step failed; the installation is put back as it was. restart: Home Assistant itself has to be restarted before
    a new attempt can work (an entry that cannot be stopped, or an old state that could not be put back)."""
    restart = False
    reason = ""  # "notstarted": put back completely, the old entries did not start again; "rollback": putting back failed too
    half = False  # an earlier move was left halfway and cannot be finished by itself: nothing was changed now, but the state is not "as before"


class FilesChanged(MoveFailure):
    """An old stored file changed while it was being copied (the old code of situation B was still saving)."""


# The old code (1.4.6) saves some of its domain-level stores after a delay of ten seconds (e32_comfort.py PresenceMemory,
# and its domain-level share store). Home Assistant has no public way to flush a Store that another integration owns, and a Store whose owner
# is unloaded still writes when its timer fires (helpers/storage.py async_delay_save): the move waits that delay out, once,
# after it has stopped the old code, plus a margin. Only in situation B (something was running); situation A waits for nothing.
_SETTLE_SECONDS = 12.0
_FILE_RETRIES = 2  # a changed file: the files step is done again, at most this many more times


@dataclass
class MoveResult:
    status: str  # moved | nothing | blocked | failed | undone | no_snapshot
    entries: int = 0
    detail: str = ""
    old_folder: bool = False
    steps: list[str] = field(default_factory=list)
    to_setup: list[str] = field(default_factory=list)
    reason: str = ""  # "restart": the user has to restart Home Assistant (and try again); "notstarted", "rollback" (see MoveFailure); "unsaved": the commit did not reach the disk; "half": an earlier move was left halfway; the text says so


def inject_failure(step: str | None, after: int = 0) -> None:
    """Tests only: the next move raises before item `after` of `step` (None: no failure)."""
    global _inject
    _inject = None if step is None else (step, after)


def _checkpoint(step: str, done: int = 0) -> None:
    if _inject is not None and _inject == (step, done):
        raise MoveFailure(f"injected failure in {step} after {done}")


# -- what is there ------------------------------------------------------------------------------------------------
def old_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    return list(hass.config_entries.async_entries(OLD_DOMAIN))


def pending(hass: HomeAssistant) -> bool:
    """Entries of the old name exist: the installation has not been moved yet."""
    return bool(old_entries(hass))


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, SNAPSHOT_VERSION, SNAPSHOT_KEY, private=True)


def _plain(value: Any) -> Any:
    """JSON-plain copy (the registries hold sets, datetimes and mappings)."""
    return json.loads(json_bytes(value))


async def load_snapshot(hass: HomeAssistant) -> dict | None:
    doc = await _store(hass).async_load()
    return doc if isinstance(doc, dict) else None


def _old_folder(hass: HomeAssistant) -> bool:
    return Path(hass.config.path("custom_components", OLD_DOMAIN)).is_dir()


# -- the snapshot -------------------------------------------------------------------------------------------------
def _entry_doc(entry: ConfigEntry) -> dict:
    return _plain(entry.as_dict()) | {"state": str(entry.state), "disabled": entry.disabled_by is not None}


def _issue_doc(issue: ir.IssueEntry) -> dict:
    return {"issue_id": issue.issue_id, "is_fixable": issue.is_fixable, "is_persistent": issue.is_persistent,
            "severity": str(issue.severity), "translation_key": issue.translation_key,
            "translation_placeholders": _plain(issue.translation_placeholders), "learn_more_url": issue.learn_more_url,
            "data": _plain(issue.data), "dismissed_version": issue.dismissed_version,
            "issue_domain": issue.issue_domain, "breaks_in_ha_version": issue.breaks_in_ha_version,
            "config_entry_id": getattr(issue, "config_entry_id", None)}


def _ident_domain(identifier) -> str | None:
    """The domain part of a device identifier. Home Assistant allows a tuple of any length (a HomeKit bridge uses three
    parts); nothing here may unpack one as a pair."""
    return identifier[0] if isinstance(identifier, (tuple, list)) and identifier else None


def _has_domain(device, domain: str) -> bool:
    return any(_ident_domain(identifier) == domain for identifier in device.identifiers)


def _retag_identifier(identifier, frm: str, to: str) -> tuple:
    """The identifier of the old domain under the new one (the rest as it is); any other identifier untouched."""
    if _ident_domain(identifier) == frm:
        return (to, *tuple(identifier)[1:])
    return tuple(identifier)


def _collect(hass: HomeAssistant, entries: list[ConfigEntry]) -> dict:
    ids = {entry.entry_id for entry in entries}
    entities = [{"entity_id": row.entity_id, "platform": row.platform, "unique_id": row.unique_id,
                 "config_entry_id": row.config_entry_id, "config_subentry_id": row.config_subentry_id,
                 "device_id": row.device_id, "name": row.name, "area_id": row.area_id,
                 "disabled_by": str(row.disabled_by) if row.disabled_by else None,
                 "hidden_by": str(row.hidden_by) if row.hidden_by else None}
                for row in er.async_get(hass).entities.values() if row.platform == OLD_DOMAIN]
    devices = [{"id": device.id, "identifiers": sorted((list(i) for i in device.identifiers), key=repr),
                "name": device.name, "name_by_user": device.name_by_user, "area_id": device.area_id}
               for device in _devices_of(hass, ids) if _has_domain(device, OLD_DOMAIN)]
    issues = [_issue_doc(issue) for (domain, _), issue in ir.async_get(hass).issues.items() if domain == OLD_DOMAIN]
    return {"entries": [_entry_doc(entry) for entry in entries], "entities": entities, "devices": devices,
            "issues": issues, "entry_ids": sorted(ids)}


def _devices_of(hass: HomeAssistant, entry_ids) -> list[dr.DeviceEntry]:
    """The devices that belong to these config entries (no mapping access: the registry's own helper)."""
    registry = dr.async_get(hass)
    found: dict[str, dr.DeviceEntry] = {}
    for entry_id in sorted(entry_ids):
        for device in dr.async_entries_for_config_entry(registry, entry_id):
            found[device.id] = device
    return list(found.values())


def _blockers(hass: HomeAssistant, entries: list[ConfigEntry]) -> str | None:
    """Anything under the new name that the move would collide with (checked before anything changes)."""
    for entry in entries:
        for other in hass.config_entries.async_entries(DOMAIN):
            if other.entry_id == entry.entry_id or (entry.unique_id is not None and other.unique_id == entry.unique_id):
                return f"an installation under the new name already exists ({entry.unique_id})"
    devices = dr.async_get(hass)
    for entry in entries:  # identifiers are unique per config entry
        for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
            for identifier in device.identifiers:
                if _ident_domain(identifier) != OLD_DOMAIN or len(identifier) < 2:
                    continue
                if devices.async_get_device_by_identifier(_retag_identifier(identifier, OLD_DOMAIN, DOMAIN), entry.entry_id) is not None:
                    return f"a device with identifier {identifier[1]} already exists under the new name"
    registry = er.async_get(hass)
    for row in list(registry.entities.values()):
        if row.platform == OLD_DOMAIN and registry.async_get_entity_id(row.domain, DOMAIN, row.unique_id) is not None:
            return f"an entity with unique id {row.unique_id} already exists under the new name"
    return None


# -- files (blocking; run in the executor) ------------------------------------------------------------------------
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_store_of_ours(path: Path) -> bool:
    """A store file as Home Assistant's Store writes it for this key. What Home Assistant itself leaves beside one
    (<key>.corrupt.<time> of a store it could not read, a temporary file) names another key or is no JSON: not ours."""
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and doc.get("key") == path.name and "version" in doc and "data" in doc


def _list_old_files(config_dir: Path) -> dict:
    storage = config_dir / ".storage"
    files = []
    left = []  # files under the old name that are not stores of ours: left where they are
    if storage.is_dir():
        for path in sorted(storage.iterdir()):
            if path.is_file() and (path.name.startswith(OLD_DOMAIN + ".") or path.name.startswith(OLD_DOMAIN + "_")):
                if _is_store_of_ours(path):
                    files.append({"name": path.name, "sha256": _sha(path), "size": path.stat().st_size})
                else:
                    left.append(path.name)
    tester = config_dir / f"{OLD_DOMAIN}_tester"
    folder = []
    if tester.is_dir():
        folder = [{"name": p.name, "sha256": _sha(p), "size": p.stat().st_size} for p in sorted(tester.iterdir()) if p.is_file()]
    return {"storage": files, "tester": folder, "left": left}


def _new_name(name: str) -> str:
    return DOMAIN + name[len(OLD_DOMAIN):]


def _read_old(config_dir: Path, listing: dict) -> list[dict]:
    """The old store files as they are now (blocking). Each must still be what the listing recorded."""
    storage = config_dir / ".storage"
    items = []
    for item in listing["storage"]:
        src = storage / item["name"]
        raw = src.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise FilesChanged(f"{item['name']} changed while it was copied")
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = None
        items.append({"name": item["name"], "doc": doc, "private": (src.stat().st_mode & 0o077) == 0})
    return items


_UNREADABLE = object()  # a file that is there and cannot be read as JSON: it differs from anything we would write


def _json_or_none(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except ValueError:  # JSONDecodeError and UnicodeDecodeError: half a file after a power cut, or made by hand
        return _UNREADABLE


def _set_aside(path: Path) -> Path:
    """A file of the new name that differs (an earlier move that was undone, then the old version ran on): the old files
    are the current ones; the other file stays beside it, never lost."""
    backup = path.with_name(path.name + ".replaced")
    n = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.replaced{n}")
        n += 1
    os.replace(path, backup)
    return backup


async def _copy_storage(hass: HomeAssistant, config_dir: Path, listing: dict, created: list[str],
                        aside: list[tuple[str, str]] | None = None) -> dict:
    """.storage/open_thermostat.* to emthera.*: written through Home Assistant's own Store, because Home Assistant has
    listed the files of .storage at its start and treats a key that was not in that list as absent: a file written beside
    the Store would not be read until the next restart (and the integration would start empty and overwrite it)."""
    done = {"created": [], "equal": [], "replaced": []}
    for item in await hass.async_add_executor_job(_read_old, config_dir, listing):
        doc = item["doc"]
        if not (isinstance(doc, dict) and doc.get("key") == item["name"] and "version" in doc and "data" in doc):
            raise MoveFailure(f"{item['name']} is not a Home Assistant store file")
        new_name = _new_name(item["name"])
        dst = config_dir / ".storage" / new_name
        expected = {"version": doc["version"], "minor_version": doc.get("minor_version", 1), "key": new_name, "data": doc["data"]}
        existing = await hass.async_add_executor_job(_json_or_none, dst)
        if existing == expected:
            done["equal"].append(new_name)
            continue
        if existing is not None:
            backup = await hass.async_add_executor_job(_set_aside, dst)
            if aside is not None:
                aside.append((new_name, backup.name))  # a failed move puts it back
            done["replaced"].append(new_name)
        store = Store(hass, doc["version"], new_name, private=item["private"], minor_version=doc.get("minor_version", 1))
        created.append(new_name)  # from here a failed move takes this file away again
        await store.async_save(doc["data"])
        if await hass.async_add_executor_job(_json_or_none, dst) != expected:
            raise MoveFailure(f"{new_name} could not be read back")
        done["created"].append(new_name)
    return done


def _copy_tester(config_dir: Path, listing: dict, created: list[str]) -> dict:
    """The tester's folder: files not there yet are copied and compared (blocking)."""
    done = {"created": [], "equal": [], "replaced": []}
    if listing["tester"]:
        old = config_dir / f"{OLD_DOMAIN}_tester"
        new = config_dir / f"{DOMAIN}_tester"
        new.mkdir(parents=True, exist_ok=True)
        for item in listing["tester"]:
            src, dst = old / item["name"], new / item["name"]
            if dst.exists():
                (done["equal"] if _sha(dst) == item["sha256"] else done["replaced"]).append(f"{new.name}/{dst.name}")
                continue
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise FilesChanged(f"{item['name']} changed while it was copied")
            tmp = dst.with_name(dst.name + ".part")
            created.append(f"{new.name}/{dst.name}")
            tmp.write_bytes(data)
            os.replace(tmp, dst)
            if _sha(dst) != item["sha256"]:
                raise MoveFailure(f"{dst.name} could not be read back")
            done["created"].append(f"{new.name}/{dst.name}")
    return done


def _old_files_unchanged(config_dir: Path, listing: dict) -> bool:
    now = _list_old_files(config_dir)
    return all(now[key] == listing[key] for key in ("storage", "tester"))  # what was left is not ours to compare


def _log_left(listing: dict) -> None:
    if listing.get("left"):
        _LOGGER.info("The move to Emthera leaves %d file(s) under the old name where they are (not stores of this integration, "
                     "not copied): %s", len(listing["left"]), ", ".join(listing["left"]))


def _put_back(config_dir: Path, aside: list[tuple[str, str]]) -> None:
    """A move that failed: a file of the new name that the move set aside goes back under its own name (C5)."""
    storage = config_dir / ".storage"
    for name, backup in reversed(aside):
        try:
            os.replace(storage / backup, storage / name)
        except OSError:
            _LOGGER.error("Could not put %s back under its name; it is still there as %s", name, backup)


async def _copy_files(hass: HomeAssistant, config_dir: Path, snapshot: dict, store: Store, created: list[str],
                      aside: list[tuple[str, str]]) -> dict:
    """The files step. An old file that changed while it was copied (the old code saving late) makes the step start
    over from a fresh listing, at most _FILE_RETRIES more times; then the move fails (and is tried again by itself once)."""
    for attempt in range(_FILE_RETRIES + 1):
        listing = snapshot["files"]
        try:
            copied = await _copy_storage(hass, config_dir, listing, created, aside)
            tester = await hass.async_add_executor_job(_copy_tester, config_dir, listing, created)
            copied = {key: copied[key] + tester[key] for key in copied}
            if not await hass.async_add_executor_job(_old_files_unchanged, config_dir, listing):
                raise FilesChanged("an old stored file changed during the move")
            copied["replaced"] = sorted(set(copied["replaced"]) | {name for name, _ in aside})
            return copied
        except FilesChanged as err:
            if attempt == _FILE_RETRIES:
                raise
            _LOGGER.info("An old stored file changed while it was copied (%s); copying again (%d of %d)", err, attempt + 1, _FILE_RETRIES)
            await hass.async_add_executor_job(_remove_created, config_dir, created)
            created.clear()
            snapshot["files"] = await hass.async_add_executor_job(_list_old_files, config_dir)
            await store.async_save(snapshot)
    raise AssertionError("unreachable")  # pragma: no cover


def _remove_created(config_dir: Path, created: list[str]) -> None:
    """A move that failed: take away the files this attempt made (only those; never an old file)."""
    for name in created:
        path = config_dir / name if "/" in name else config_dir / ".storage" / name
        if path.name.startswith(OLD_DOMAIN):
            continue
        try:
            path.unlink()
        except OSError:
            pass


# -- HomeKit: the accessory ids of our entities (review finding A2) --------------------------------------------------
# HomeKit's bridge remembers the accessory id (aid) of an entity under the key "<platform>.<domain>.<unique id>"
# (homeassistant/components/homekit/aidmanager.py:36-38, lookup 143-150 and 174-190) in .storage/homekit.<entry id>.aids
# (homekit/util.py:638-640; Store version 1, aidmanager.py:23 and 81; the allocations are under "allocations", :26).
# The move changes the platform of every row of ours, so the keys are carried along to the new platform name first:
# a bridge that is loaded holds them in memory (entry.runtime_data.homekit.aid_storage.allocations, homekit/__init__.py:
# 284-287 and 380, models.py:15-20) and is changed there in the same synchronous stretch as the rows; any other bridge
# has only its file. HomeKit is not ours: whatever is not as expected leaves that bridge exactly as it was and is said.
HOMEKIT = "homekit"
_HK_VERSION = 1


def _hk_pairs(rows, frm: str, to: str) -> dict[str, str]:
    """Old key -> new key of each row of the old platform (the key rule of aidmanager.get_system_unique_id)."""
    return {f"{frm}.{row.domain}.{row.unique_id}": f"{to}.{row.domain}.{row.unique_id}"
            for row in rows if row.platform == frm and isinstance(row.unique_id, str)}


def _hk_plan(allocations: dict, mapping: dict[str, str], aids: dict[str, int] | None = None) -> list[tuple[str, str, int]] | str:
    """The renames (old, new, id) to make in this allocations dict, or why they cannot be made (then none are)."""
    moves = []
    for old, new in mapping.items():
        if old not in allocations:
            continue
        aid = allocations[old]
        if type(aid) is not int:
            return "an accessory id is not a number"
        if aids is not None and aids.get(old) != aid:
            return "an accessory id is not the one that was carried"
        if new in allocations:
            if allocations[new] == aid:
                continue
            return "the new key already holds another accessory id"
        moves.append((old, new, aid))
    return moves


def _hk_plan_types(types: Any, mapping: dict[str, str], values: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    """The renames of the stored accessory types (aidmanager.py:99,121: the same key rule). A type that cannot be carried
    (the new key holds another type, the value is not text) stays as it is and is no reason to leave the bridge alone."""
    moves = []
    for old, new in mapping.items() if isinstance(types, dict) else ():
        if old not in types:
            continue
        value = types[old]
        if not isinstance(value, str) or (values is not None and values.get(old) != value):
            continue
        if new in types:
            if types[new] != value:
                _LOGGER.debug("HomeKit accessory type of %s left as it is: the new key holds another type", new)
            continue
        moves.append((old, new, value))
    return moves


def _hk_maps(items: list[dict], back: bool) -> tuple[dict, dict | None, dict, dict | None]:
    """(id mapping, ids to expect, type mapping, types to expect) of one bridge's listed items, forwards or back."""
    ids = [i for i in items if i.get("section", "allocations") == "allocations"]
    types = [i for i in items if i.get("section") == "accessory_types"]
    a, b = ("new", "old") if back else ("old", "new")
    return ({i[a]: i[b] for i in ids}, {i[a]: i["aid"] for i in ids} if back else None,
            {i[a]: i[b] for i in types}, {i[a]: i["value"] for i in types} if back else None)


def _hk_mode(entry: ConfigEntry) -> tuple[str, Any]:
    """live (its storage is in memory), file (only its file) or odd:<why> (a loaded bridge that is not shaped as expected)."""
    if entry.state is not ConfigEntryState.LOADED:
        return "file", None
    homekit = getattr(getattr(entry, "runtime_data", None), "homekit", None)
    if homekit is None:
        return "odd:the loaded bridge has no HomeKit object", None
    storage = getattr(homekit, "aid_storage", None)
    if storage is None:
        return "file", None  # not started yet: it reads its file when it starts
    allocations = getattr(storage, "allocations", None)
    if not isinstance(allocations, dict):
        return "odd:its allocations are not a dictionary", None
    if not allocations:
        return "file", None  # empty in memory: nothing to change there (or its file is still being read: the file is the truth)
    if not callable(getattr(storage, "async_schedule_save", None)):
        return "odd:it cannot schedule a save", None
    return "live", storage


def _hk_item(entry_id: str, move_: tuple[str, str, int], route: str) -> dict:
    return {"entry_id": entry_id, "old": move_[0], "new": move_[1], "aid": move_[2], "route": route, "section": "allocations"}


def _hk_type_item(entry_id: str, move_: tuple[str, str, str], route: str) -> dict:
    return {"entry_id": entry_id, "old": move_[0], "new": move_[1], "value": move_[2], "route": route, "section": "accessory_types"}


def _hk_not_carried(hk: dict, entry: ConfigEntry, why: str) -> None:
    """Leave this bridge as it is, say so once, and remember it (the notice tells the user)."""
    if any(item["entry_id"] == entry.entry_id for item in hk["not_carried"]):
        return
    hk["carried"] = [item for item in hk["carried"] if item["entry_id"] != entry.entry_id]
    hk["not_carried"].append({"entry_id": entry.entry_id, "reason": why})
    _LOGGER.warning("HomeKit bridge %s was left as it was, so Apple Home will see the thermostats of this installation as "
                    "new accessories: %s", entry.entry_id, why)


def _hk_file_path(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(".storage", f"{HOMEKIT}.{entry_id}.aids"))


def _hk_read_file(path: Path) -> tuple[dict, bytes] | None:
    """The aid file as HomeKit wrote it (blocking). None: there is no file. ValueError: it is not shaped as expected."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    doc = json.loads(raw)
    if not (isinstance(doc, dict) and doc.get("key") == path.name and doc.get("version") == _HK_VERSION
            and type(doc.get("minor_version", 1)) is int and isinstance(doc.get("data"), dict)
            and isinstance(doc["data"].get("allocations", {}), dict)):
        raise ValueError("the aid file is not shaped as HomeKit writes it")
    return doc, raw


def _hk_write_back(path: Path, raw: bytes) -> None:
    if path.read_bytes() != raw:
        path.write_bytes(raw)


async def _hk_file_pass(hass: HomeAssistant, entry_id: str, mapping: dict[str, str], aids: dict[str, int] | None = None,
                        tmapping: dict[str, str] | None = None, tvalues: dict[str, str] | None = None) -> str | None:
    """Rename keys in the aid file of a bridge that is not loaded, through the Store HomeKit uses (same key and version),
    read back and compared. None: done or nothing to do. Else why the file was left as it is (put back byte for byte)."""
    path = _hk_file_path(hass, entry_id)
    raw = b""
    try:
        found = await hass.async_add_executor_job(_hk_read_file, path)
        if found is None:
            return None
        doc, raw = found
        allocations = doc["data"].get("allocations", {})
        moves = _hk_plan(allocations, mapping, aids)
        if isinstance(moves, str):
            return moves
        tmoves = _hk_plan_types(doc["data"].get("accessory_types"), tmapping or {}, tvalues)
        if not moves and not tmoves:
            return None
        rename = {old: new for old, new, _ in moves}
        data = {**doc["data"], "allocations": {rename.get(key, key): value for key, value in allocations.items()}}
        if tmoves:
            trename = {old: new for old, new, _ in tmoves}
            data["accessory_types"] = {trename.get(key, key): value for key, value in doc["data"]["accessory_types"].items()}
        store = Store(hass, _HK_VERSION, path.name, minor_version=doc.get("minor_version", 1))
        await store.async_save(data)
        again = await hass.async_add_executor_job(_hk_read_file, path)
        if again is None or again[0]["data"] != data or again[0].get("key") != path.name:
            raise ValueError("the aid file could not be read back")
        return None
    except Exception as err:  # noqa: BLE001 - HomeKit is not ours: whatever happens, the file goes back as it was
        try:
            if raw:
                await hass.async_add_executor_job(_hk_write_back, path, raw)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("the aid file of bridge %s could not be put back", entry_id, exc_info=True)
        return f"{type(err).__name__}: {err}"


def _hk_live_pass(storage: Any, mapping: dict[str, str], aids: dict[str, int] | None = None,
                  tmapping: dict[str, str] | None = None, tvalues: dict[str, str] | None = None) -> str | None:
    """Rename keys in the allocations of a loaded bridge and schedule HomeKit's own save (synchronous; all or nothing)."""
    allocations = storage.allocations
    moves = _hk_plan(allocations, mapping, aids)
    if isinstance(moves, str):
        return moves
    types = getattr(storage, "accessory_types", None)
    tmoves = _hk_plan_types(types, tmapping or {}, tvalues)
    done, tdone = [], []
    try:
        for old, new, aid in moves:
            allocations[new] = allocations.pop(old)
            done.append((old, new))
        for old, new, value in tmoves:
            types[new] = types.pop(old)
            tdone.append((old, new))
        if done or tdone:
            storage.async_schedule_save()
    except Exception as err:  # noqa: BLE001
        for old, new in reversed(tdone):
            types[old] = types.pop(new)
        for old, new in reversed(done):
            allocations[old] = allocations.pop(new)
        return f"{type(err).__name__}: {err}"
    return None


async def _homekit_plan(hass: HomeAssistant, snapshot: dict) -> None:
    """Before the registries change: which keys of which bridges are carried (read only; nothing is written). Never raises."""
    hk = snapshot["homekit"] = {"carried": [], "not_carried": []}
    try:
        pairs = _hk_pairs(er.async_get(hass).entities.values(), OLD_DOMAIN, DOMAIN)
        for entry in hass.config_entries.async_entries(HOMEKIT) if pairs else []:
            try:
                mode, storage = _hk_mode(entry)
                if mode.startswith("odd:"):
                    _hk_not_carried(hk, entry, mode[4:])
                    continue
                if mode == "live":
                    moves = _hk_plan(storage.allocations, pairs)
                    tmoves = _hk_plan_types(getattr(storage, "accessory_types", None), pairs)
                else:
                    found = await hass.async_add_executor_job(_hk_read_file, _hk_file_path(hass, entry.entry_id))
                    moves = [] if found is None else _hk_plan(found[0]["data"].get("allocations", {}), pairs)
                    tmoves = [] if found is None else _hk_plan_types(found[0]["data"].get("accessory_types"), pairs)
                if isinstance(moves, str):
                    _hk_not_carried(hk, entry, moves)
                    continue
                hk["carried"] += [_hk_item(entry.entry_id, one, mode) for one in moves]
                hk["carried"] += [_hk_type_item(entry.entry_id, one, mode) for one in tmoves]
            except Exception as err:  # noqa: BLE001
                _hk_not_carried(hk, entry, f"{type(err).__name__}: {err}")
    except Exception:  # noqa: BLE001
        _LOGGER.warning("HomeKit accessory ids could not be looked at; the move goes on", exc_info=True)


def _hk_by_entry(hk: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in hk.get("carried", []):
        grouped.setdefault(item["entry_id"], []).append(item)
    return grouped


async def _homekit_write_files(hass: HomeAssistant, snapshot: dict) -> None:
    """The planned renames of the bridges that are not loaded (awaits; the snapshot already lists them). Never raises."""
    hk = snapshot.get("homekit") or {}
    try:
        for entry_id, items in _hk_by_entry(hk).items():
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or items[0]["route"] != "file":
                continue
            why = await _hk_file_pass(hass, entry_id, *_hk_maps(items, False))
            if why:
                _hk_not_carried(hk, entry, why)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("HomeKit accessory ids could not be carried to the new name", exc_info=True)


def _homekit_live(hass: HomeAssistant, snapshot: dict, *, back: bool = False) -> None:
    """The renames of the loaded bridges, in the same synchronous stretch as the rows (no await between). Never raises.
    back: the other way round (the undo and the restore of a failed move). A bridge that was planned as a file and has
    started since is looked at too: it may hold the old keys in memory."""
    hk = snapshot.get("homekit") or {}
    try:
        for entry_id, items in _hk_by_entry(hk).items():
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            mode, storage = _hk_mode(entry)
            planned_live = items[0]["route"] == "live"
            if mode == "live":
                why = _hk_live_pass(storage, *_hk_maps(items, back))
            elif back or not planned_live:
                continue  # back: the file route handles it; forward: a file that was written is not undone by a bridge that started
            elif mode.startswith("odd:"):
                why = mode[4:]
            else:
                why = "the bridge was stopped while the move was running"
            if why and back:
                _LOGGER.warning("HomeKit bridge %s: the old accessory keys could not be put back: %s", entry_id, why)
            elif why:
                _hk_not_carried(hk, entry, why)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("HomeKit accessory ids could not be carried to the new name", exc_info=True)


async def _homekit_back_files(hass: HomeAssistant, snapshot: dict) -> None:
    """The way back for the bridges that are not loaded (the undo, the restore of a failed move, the recovery). Never raises."""
    hk = snapshot.get("homekit") or {}
    try:
        for entry_id, items in _hk_by_entry(hk).items():
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or _hk_mode(entry)[0] != "file":
                continue
            why = await _hk_file_pass(hass, entry_id, *_hk_maps(items, True))
            if why:
                _LOGGER.warning("HomeKit bridge %s: the old accessory keys could not be put back: %s", entry_id, why)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("HomeKit accessory ids could not be put back", exc_info=True)


async def _homekit_forward_files(hass: HomeAssistant, snapshot: dict) -> None:
    """The keys of the bridges that are not loaded forward again (an undo that was taken back, the heal of a moved snapshot):
    the mirror of _homekit_back_files, idempotent. Never raises."""
    hk = snapshot.get("homekit") or {}
    try:
        for entry_id, items in _hk_by_entry(hk).items():
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or _hk_mode(entry)[0] != "file":
                continue
            why = await _hk_file_pass(hass, entry_id, *_hk_maps(items, False))
            if why:
                _LOGGER.warning("HomeKit bridge %s: the new accessory keys could not be put back: %s", entry_id, why)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("HomeKit accessory ids could not be carried to the new name", exc_info=True)


# -- the registries (synchronous: nothing else runs while they change) ---------------------------------------------
_RESET =("supports_unload", "supports_remove_device", "_supports_options", "_supports_reconfigure",
          "_supported_subentry_types", "_integration_for_domain")


def _clear_caches(entry: ConfigEntry) -> None:
    """The entry's own caches of its stored and shown form. ConfigEntry.__setattr__ clears them, but the domain is changed
    around it (it is frozen there), so they are cleared here: a save of the entries must write the new domain."""
    for name in ("clear_state_cache", "clear_storage_cache"):
        clear = getattr(entry, name, None)
        if clear is not None:
            clear()


def _stored_form_problem(entries, domain: str) -> str | None:
    """None when the form Home Assistant writes into core.config_entries names this domain for every entry, else why not."""
    for entry in entries:
        try:
            stored = json.loads(json_bytes(entry.as_storage_fragment))["domain"]
        except Exception as err:  # noqa: BLE001 - whatever way the form cannot be read, the move must not trust it
            return f"the stored form of {entry.title!r} cannot be read ({type(err).__name__})"
        if stored != domain or entry.as_dict().get("domain") != domain or entry.domain != domain:
            return f"the stored form of {entry.title!r} does not name {domain}"
    return None


def _set_domain(hass: HomeAssistant, entry: ConfigEntry, domain: str) -> None:
    """Change an entry's domain in place (same object, same id): the entries container re-indexes it."""
    items = hass.config_entries._entries  # noqa: SLF001 - there is no public way to change an entry's domain
    if entry.domain == domain:
        return
    del items[entry.entry_id]
    object.__setattr__(entry, "domain", domain)
    for name in _RESET:
        if hasattr(entry, name):
            object.__setattr__(entry, name, None)
    items[entry.entry_id] = entry
    entry._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)  # noqa: SLF001
    _clear_caches(entry)
    hass.config_entries._async_schedule_save()  # noqa: SLF001


def _platform_of(hass: HomeAssistant, row: er.RegistryEntry, new_platform: str) -> None:
    registry = er.async_get(hass)
    kwargs: dict[str, Any] = {}
    if row.config_entry_id is not None:
        kwargs["new_config_entry_id"] = row.config_entry_id
        if "new_config_subentry_id" in inspect.signature(registry.async_update_entity_platform).parameters:
            kwargs["new_config_subentry_id"] = row.config_subentry_id
    registry.async_update_entity_platform(row.entity_id, new_platform, **kwargs)
    # The integration keeps per-entity options under its own name (REPORTED, TWIN_OF, the shown live flow ...): they move too.
    carried = row.options.get(row.platform)
    if carried:
        registry.async_update_entity_options(row.entity_id, new_platform, dict(carried))
        registry.async_update_entity_options(row.entity_id, row.platform, None)


def _retag_devices(hass: HomeAssistant, frm: str, to: str, entry_ids: set[str] | None = None) -> int:
    devices = dr.async_get(hass)
    count = 0
    for device in _devices_of(hass, entry_ids or ()):
        if not _has_domain(device, frm):
            continue
        identifiers = {_retag_identifier(identifier, frm, to) for identifier in device.identifiers}
        devices.async_update_device(device.id, new_identifiers=identifiers)
        count += 1
    return count


def _retag_entities(hass: HomeAssistant, frm: str, to: str, entry_ids: set[str] | None = None, also=frozenset()) -> int:
    """also: entity ids that move whatever their config entry (rows of the platform that have none)."""
    registry = er.async_get(hass)
    count = 0
    for row in list(registry.entities.values()):
        if row.platform != frm:
            continue
        if entry_ids is not None and row.config_entry_id not in entry_ids and row.entity_id not in also:
            continue
        _platform_of(hass, row, to)
        count += 1
    return count


def _drop_issues(hass: HomeAssistant, domain: str) -> int:
    count = 0
    for (issue_domain, issue_id) in list(ir.async_get(hass).issues):
        if issue_domain == domain:
            ir.async_delete_issue(hass, domain, issue_id)
            count += 1
    return count


def _issue_extras(doc: dict) -> dict:
    """The fields of a repair that older snapshots do not hold, and (config_entry_id) older Home Assistant versions do not know."""
    extras = {"issue_domain": doc.get("issue_domain"), "breaks_in_ha_version": doc.get("breaks_in_ha_version")}
    if "config_entry_id" in inspect.signature(ir.async_create_issue).parameters:
        extras["config_entry_id"] = doc.get("config_entry_id")
    return extras


def _recreate_issues(hass: HomeAssistant, documents: list[dict]) -> None:
    for doc in documents:
        severity = str(doc.get("severity", "warning")).rsplit(".", 1)[-1].lower()
        ir.async_create_issue(
            hass, OLD_DOMAIN, doc["issue_id"], is_fixable=bool(doc.get("is_fixable")),
            is_persistent=bool(doc.get("is_persistent")), severity=ir.IssueSeverity(severity),
            translation_key=doc.get("translation_key"), translation_placeholders=doc.get("translation_placeholders"),
            learn_more_url=doc.get("learn_more_url"), data=doc.get("data"), **_issue_extras(doc))
        if doc.get("dismissed_version"):
            ir.async_ignore_issue(hass, OLD_DOMAIN, doc["issue_id"], True)


def _restore_registries(hass: HomeAssistant, snapshot: dict, *, entry_ids: set[str], drop_new_issues: bool = False) -> str | None:
    """Everything back to the old name. Idempotent: it sets the old state whatever part of the move happened.
    Returns None, or why the stored form of an entry does not name the old domain after all."""
    _homekit_live(hass, snapshot, back=True)  # the same synchronous stretch as the rows below
    originals = {doc["entry_id"]: doc for doc in snapshot.get("entries", [])}
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            continue
        original = originals.get(entry_id)
        if original is not None:  # only what the move itself changed: the prefix its base step added; the rest stays as it is now
            before = original["data"].get(CONF_TOPIC_PREFIX)
            if not isinstance(before, str) or not before:
                data = {key: value for key, value in entry.data.items() if key != CONF_TOPIC_PREFIX}
                if before is not None:
                    data[CONF_TOPIC_PREFIX] = before
                if data != dict(entry.data):
                    hass.config_entries.async_update_entry(entry, data=data)
        _set_domain(hass, entry, OLD_DOMAIN)
    _retag_entities(hass, DOMAIN, OLD_DOMAIN, entry_ids, also={e["entity_id"] for e in snapshot.get("entities", [])})
    _retag_devices(hass, DOMAIN, OLD_DOMAIN, entry_ids)
    if drop_new_issues:
        _drop_issues(hass, DOMAIN)
    have = {issue_id for (domain, issue_id) in ir.async_get(hass).issues if domain == OLD_DOMAIN}
    _recreate_issues(hass, [d for d in snapshot.get("issues", []) if d["issue_id"] not in have])
    problem = _stored_form_problem([e for e in (hass.config_entries.async_get_entry(i) for i in entry_ids) if e is not None], OLD_DOMAIN)
    if problem:
        _LOGGER.error("After putting the old names back: %s", problem)
    return problem


# -- the move -----------------------------------------------------------------------------------------------------
def _lock(hass: HomeAssistant) -> asyncio.Lock:
    return hass.data.setdefault(_LOCK, asyncio.Lock())


async def async_move(hass: HomeAssistant, trigger: str = "user") -> MoveResult:
    """Move every installation of the old name. Safe to call at any time and from several places at once."""
    async with _lock(hass):
        try:
            result = await _move(hass, trigger)
        except MoveFailure as err:
            if err.half:  # nothing was changed now, and nothing was undone: the earlier move is still halfway
                _LOGGER.error("An earlier move to Emthera was left halfway and cannot be finished by itself: %s", err)
                return MoveResult("failed", detail=str(err), reason="half")
            # With the traceback: a failure nobody foresaw must be findable from the log alone.
            _LOGGER.error("The move to Emthera did not complete and was undone: %s", err, exc_info=err.__cause__)  # None for a failure we named ourselves
            return MoveResult("failed", detail=str(err), reason=err.reason or ("restart" if err.restart else ""))
    # Outside the lock: setting up the integration runs its async_setup, which takes the same lock.
    for entry_id in result.to_setup:
        try:
            await hass.config_entries.async_setup(entry_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("The moved installation %s could not be set up", entry_id)
    return result


def _finished_under_new_names(hass: HomeAssistant, doc: dict) -> bool:
    """An in-progress snapshot whose registries are completely under the new name (and nothing of it is gone)."""
    rows, old_devices, entries, gone = _left_under_old_name(hass, doc)
    ids = doc.get("entry_ids", [])
    new = [e for i in ids if (e := hass.config_entries.async_get_entry(i)) is not None and e.domain == DOMAIN]
    return bool(ids) and not (rows or old_devices or entries or gone) and len(new) == len(ids)


def _undo_was_interrupted(doc: dict) -> bool:
    """In-progress snapshot of an UNDO (the action emthera.undo_move stopped halfway) or of a MOVE? A snapshot that went
    through the commit of a move carries "finished" (written only there); an undo starts from such a snapshot, a move
    interrupted before its commit has none. The undo also says so itself: "interrupted": "undo" beside the status."""
    return doc.get("interrupted") == "undo" or bool(doc.get("finished"))


async def _recover(hass: HomeAssistant, doc: dict | None) -> str | None:
    """A snapshot that still says in_progress: Home Assistant stopped during a move or an undo; put the old names back
    (both end at the old names). Returns "move", "undo" or None. An interrupted move may be tried again by the automatic
    path once (doc["retry"]); an interrupted undo is finished: the snapshot says undone and nothing moves again by itself."""
    if doc and doc.get("status") == IN_PROGRESS:
        undo = _undo_was_interrupted(doc)
        _LOGGER.warning("An earlier %s was interrupted; putting the old names back first", "undo of the move to Emthera" if undo
                        else "move to Emthera")
        if undo:
            disable_aliases(hass)  # as the undo itself does first
        if not undo and _finished_under_new_names(hass, doc):
            # The commit did not reach the disk (Home Assistant's Store swallows a write error) but every row, device and entry
            # IS under the new name: the move ends moved, it is not put back.
            _LOGGER.warning("A move to Emthera was complete but its snapshot still said in progress; it is marked moved now")
            doc.update(status=MOVED, finished=dt_util.utcnow().isoformat())
            await _store(hass).async_save(doc)
            return "moved"
        await _homekit_back_files(hass, doc)  # the HomeKit keys of a bridge that is not loaded go back with the rows (move and undo alike)
        problem = _restore_registries(hass, doc, entry_ids=set(doc.get("entry_ids", [])), drop_new_issues=undo)
        if problem:  # the snapshot stays in progress: nothing says "failed" or "undone" over a state that is not put back
            failure = MoveFailure(problem)
            failure.half = True
            raise failure
        if undo:
            doc.update(status=UNDONE, undone=dt_util.utcnow().isoformat(), detail="the undo was finished at the next start")
        else:
            doc["status"], doc["detail"] = FAILED, "interrupted; restored at the next start"
            doc["retry"] = not doc.get("auto_retried")
        await _store(hass).async_save(doc)
        return "undo" if undo else "move"
    return None


async def async_ensure_recovered(hass: HomeAssistant) -> None:
    """The first time any code of this integration runs in this Home Assistant run, also when that is the config flow or
    the MQTT discovery (Home Assistant sets up the component only for config entries of its domain, and a flow does not
    set it up: bootstrap.py `_get_domains` 744-762, config_entries.py `_load_integration` 4423-4440), an interrupted move
    or undo is put right. Once per run."""
    if hass.data.get(_RECOVERED):
        return
    async with _lock(hass):
        if hass.data.get(_RECOVERED):
            return
        doc = await _store(hass).async_load()
        doc = doc if isinstance(doc, dict) else None
        try:
            if kind := await _recover(hass, doc):
                _after_recovery(hass, doc, kind)
        except Exception:  # noqa: BLE001 - the flow must still open; the start of the component reports it
            _LOGGER.exception("An earlier move to Emthera could not be put right")
        hass.data[_RECOVERED] = True


def _after_recovery(hass: HomeAssistant, doc: dict, kind: str = "move") -> None:
    """The start found an interrupted move and put the old names back (B9). Nothing may stay silent: with the old code
    present (situation B) its entries run again in this same run; without it (situation A) the user is told."""
    entries = [hass.config_entries.async_get_entry(i) for i in doc.get("entry_ids", [])]
    again = [e for e in entries if e is not None and e.domain == OLD_DOMAIN and e.disabled_by is None
             and e.state is ConfigEntryState.NOT_LOADED]
    if _old_folder(hass):
        for entry in again:
            hass.async_create_task(hass.config_entries.async_setup(entry.entry_id), f"emthera: old entry {entry.title} runs again")
    elif kind == "move":
        notify_failed(hass, doc.get("detail", ""))
    # kind "moved": nothing to say; the moved snapshot goes on to the heal and the aliases


async def _unload_all(hass: HomeAssistant, entry_ids: list[str], stopped: list[str]) -> None:
    """Stop these entries one after the other, all together within UNLOAD_LIMIT seconds. Each one that stopped is appended
    to `stopped` (so the caller can start it again). An unload that returns False, raises or does not finish is a MoveFailure;
    restart is set when Home Assistant has left the entry in a state it will not unload or set up again."""
    current = None
    try:
        async with asyncio.timeout(UNLOAD_LIMIT):
            for entry_id in entry_ids:
                current = hass.config_entries.async_get_entry(entry_id)
                try:
                    done = await hass.config_entries.async_unload(entry_id)
                except Exception:  # noqa: BLE001 - Home Assistant refuses an unload (OperationNotAllowed) or the old code raised
                    _LOGGER.exception("The old installation %s could not be stopped", current.title if current else entry_id)
                    done = False
                if not done:
                    failure = MoveFailure(f"the old installation {current.title if current else entry_id!r} could not be stopped")
                    failure.restart = current is not None and not current.state.recoverable
                    raise failure
                stopped.append(entry_id)
    except TimeoutError:
        failure = MoveFailure(f"the old installation {current.title if current else '?'!r} did not stop in time")
        failure.restart = True  # Home Assistant keeps such an entry in "unload in progress": only a restart frees it
        raise failure from None


async def _start_again(hass: HomeAssistant, entry_ids: list[str]) -> bool:
    """Set these entries up again (awaited, within UNLOAD_LIMIT seconds together). True when every one runs (or is waiting
    to retry); False when one does not: then only a restart of Home Assistant helps and the user must be told so."""
    ok = True
    try:
        async with asyncio.timeout(UNLOAD_LIMIT):
            for entry_id in entry_ids:
                entry = hass.config_entries.async_get_entry(entry_id)
                try:
                    good = bool(await hass.config_entries.async_setup(entry_id))
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("The installation %s could not be set up again", entry.title if entry else entry_id)
                    good = False
                if not good and (entry is None or entry.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)):
                    ok = False
    except TimeoutError:
        _LOGGER.error("Setting the installations up again took longer than %s seconds", UNLOAD_LIMIT)
        ok = False
    return ok


def _best_effort(what: str, func, *args, **kwargs) -> bool:
    """A step after the commit: whatever it raises is logged with its traceback and the move stays moved."""
    try:
        func(*args, **kwargs)
        return True
    except Exception:  # noqa: BLE001
        _LOGGER.exception("After the move to Emthera: %s failed (the move itself is complete)", what)
        return False


async def _saved_status(hass: HomeAssistant, status: str) -> bool:
    """Home Assistant's Store swallows a write error (helpers/storage.py _async_write_data): read the snapshot back and say
    whether it names the status that was written. Never raises."""
    try:
        on_disk = await _store(hass).async_load()
        found = on_disk.get("status") if isinstance(on_disk, dict) else on_disk
    except Exception as err:  # noqa: BLE001
        found = f"unreadable ({type(err).__name__})"
    if found == status:
        return True
    _LOGGER.error("The snapshot of the move should say %r, but on disk it says %r. The registries are already changed and "
                  "stay as they are; the next start of Home Assistant finishes what the snapshot lacks.", status, found)
    return False


async def _finish_move(hass: HomeAssistant, store: Store, snapshot: dict, entries: list[ConfigEntry], steps: list[str],
                       saved: bool = True) -> MoveResult:
    """What follows the commit. Nothing in here may raise: the snapshot says moved, so the entries must be set up."""
    old_folder = False
    try:
        old_folder = _old_folder(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("After the move to Emthera: the old folder could not be looked up")
    result = MoveResult("moved", entries=len(entries), old_folder=old_folder, steps=steps, reason="" if saved else "unsaved")
    try:
        changed = _after_move(hass, snapshot, result)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("After the move to Emthera: the follow-up work failed (the move itself is complete)")
        changed = False
    if changed:
        try:
            await store.async_save(snapshot)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("After the move to Emthera: the snapshot could not be saved with the notice marked as shown")
    result.to_setup = [entry.entry_id for entry in entries if entry.disabled_by is None]
    return result


async def _move(hass: HomeAssistant, trigger: str) -> MoveResult:
    store = _store(hass)
    try:  # what runs before the move's own try: whatever it raises is the half state's, never an exception out of async_move
        previous = await store.async_load()
        if await _recover(hass, previous if isinstance(previous, dict) else None) == "undo" and trigger != "user":
            return MoveResult("nothing")  # the user's undo, finished now: nothing moves again by itself
        if isinstance(previous, dict) and previous.get("status") == MOVED:  # a commit whose registries were not all saved (B2)
            problem, healed = await _heal_moved(hass, previous)
            if problem:
                half = MoveFailure(problem)
                half.half = True
                raise half
            if healed:
                enable_aliases(hass)
                return MoveResult("moved", entries=len(healed), old_folder=_old_folder(hass), steps=["heal"],
                                  to_setup=[i for i in healed if (e := hass.config_entries.async_get_entry(i)) and e.disabled_by is None])
    except MoveFailure:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("An earlier move to Emthera could not be put right before this one")
        half = MoveFailure(f"{type(err).__name__}: {err}")
        half.half = True
        raise half from err
    entries = old_entries(hass)
    if not entries:
        return MoveResult("nothing")
    config_dir = Path(hass.config.path())
    steps: list[str] = []
    created: list[str] = []
    aside: list[tuple[str, str]] = []  # new-name files this attempt set aside (put back if it fails)
    stopped: list[str] = []
    entry_ids = {entry.entry_id for entry in entries}
    snapshot: dict = {}
    try:
        # 1. stop what the old code started (situation B): it saves its stores when it stops, so the files are listed after
        _checkpoint("stop")
        for _ in range(90):  # an entry that Home Assistant is still starting (or unloading) is not touched: wait for it
            if not any(entry.state in (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.UNLOAD_IN_PROGRESS) for entry in entries):
                break
            await asyncio.sleep(1)
        else:
            raise MoveFailure("an old installation is still starting; try again in a minute")
        blocker = _blockers(hass, entries)
        if blocker:
            return MoveResult("blocked", detail=blocker)
        if stuck := [entry for entry in entries if entry.state is ConfigEntryState.FAILED_UNLOAD]:
            # Home Assistant refuses to unload such an entry (config_entries.py async_unload: a state that is not recoverable).
            return MoveResult("blocked", reason="restart", detail=f"the old installation {stuck[0].title!r} is stuck in a failed stop")
        was_loaded = [entry.entry_id for entry in entries
                      if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY)]
        await _unload_all(hass, was_loaded, stopped)
        steps.append("stop")
        # 2. the snapshot, written and read back before any registry or file of ours changes
        _checkpoint("snapshot")
        if stopped:  # situation B: the old code may still have a delayed save pending
            await asyncio.sleep(_SETTLE_SECONDS)
        listing = await hass.async_add_executor_job(_list_old_files, config_dir)
        _log_left(listing)
        snapshot = {"schema": 1, "status": IN_PROGRESS, "taken": dt_util.utcnow().isoformat(), "trigger": trigger,
                    "from": OLD_DOMAIN, "to": DOMAIN, **_collect(hass, entries), "files": listing, "was_loaded": was_loaded,
                    "told": bool(isinstance(previous, dict) and previous.get("told")),
                    "auto_retried": bool(isinstance(previous, dict) and previous.get("status") == FAILED and previous.get("auto_retried"))}
        await store.async_save(snapshot)
        if await _store(hass).async_load() != snapshot:
            raise MoveFailure("the snapshot could not be read back")
        steps.append("snapshot")
        # 3. the stored files, copied and compared
        _checkpoint("files")
        copied = await _copy_files(hass, config_dir, snapshot, store, created, aside)
        # HomeKit's accessory ids of our entities are carried to the new key before the rows change (finding A2): planned and
        # written into the snapshot first, so that a stopped move can put them back; nothing here can fail the move. Only
        # now, after the files step (with its retries) has succeeded: a retry of that step must not meet file writes of a bridge.
        await _homekit_plan(hass, snapshot)
        if snapshot["homekit"]["carried"] or snapshot["homekit"]["not_carried"]:
            await store.async_save(snapshot)
        await _homekit_write_files(hass, snapshot)
        steps.append("files")
        # 4. the registries: no await from here until the end of step 8
        _checkpoint("base")
        for entry in entries:
            data = dict(entry.data)
            if not isinstance(data.get(CONF_TOPIC_PREFIX), str) or not data.get(CONF_TOPIC_PREFIX):
                hass.config_entries.async_update_entry(entry, data={**data, CONF_TOPIC_PREFIX: GATEWAY_TOPIC_PREFIX})
        steps.append("base")
        _homekit_live(hass, snapshot)  # loaded bridges: their keys, in the same synchronous stretch as the rows below
        _checkpoint("devices")
        for n, device in enumerate([d for d in _devices_of(hass, entry_ids)
                                    if _has_domain(d, OLD_DOMAIN)]):
            _checkpoint("devices", n)
            _retag_one_device(hass, device)
        _checkpoint("devices", len(snapshot["devices"]))
        steps.append("devices")
        _checkpoint("entities")
        registry = er.async_get(hass)
        for n, row in enumerate([r for r in registry.entities.values() if r.platform == OLD_DOMAIN]):
            _checkpoint("entities", n)
            _platform_of(hass, row, DOMAIN)
        _checkpoint("entities", len(snapshot["entities"]))
        steps.append("entities")
        _checkpoint("entries")
        for n, entry in enumerate(entries):
            _checkpoint("entries", n)
            _set_domain(hass, entry, DOMAIN)
        _checkpoint("entries", len(entries))
        if problem := _stored_form_problem(entries, DOMAIN):  # what the next save of the entries would write
            raise MoveFailure(problem)
        steps.append("entries")
        _checkpoint("issues")
        _drop_issues(hass, OLD_DOMAIN)
        steps.append("issues")
        _verify(hass, snapshot)
        # 5. commit
        _checkpoint("commit")
        snapshot.update(status=MOVED, steps=steps, created=created, copied=copied, finished=dt_util.utcnow().isoformat())
        await store.async_save(snapshot)
        steps.append("commit")
        saved = await _saved_status(hass, MOVED)
    except BaseException as err:
        # Back to the old names (synchronously, whatever the error: also a cancelled task must not leave half a move).
        restart_needed = False
        reason = ""
        try:
            await _homekit_back_files(hass, snapshot)
            rollback_problem = _restore_registries(hass, snapshot or {"entries": [], "issues": []}, entry_ids=entry_ids)
            await hass.async_add_executor_job(_remove_created, config_dir, created)
            await hass.async_add_executor_job(_put_back, config_dir, aside)
            if rollback_problem:
                # Putting back did not hold: the snapshot stays (or becomes) in progress, which is what the recovery at the next
                # start of ours puts right. Never "failed" here, and never with the commit's stamp (that marks an undo).
                reason, restart_needed = "rollback", True
                if snapshot:
                    snapshot.pop("finished", None)
                    snapshot.update(status=IN_PROGRESS, detail=rollback_problem, steps=steps)
                    await _store(hass).async_save(snapshot)
            elif snapshot:
                snapshot.update(status=FAILED, detail=str(err) or type(err).__name__, steps=steps,
                                retry=isinstance(err, FilesChanged) and not snapshot.get("auto_retried"))
                await _store(hass).async_save(snapshot)
            # The old code ran them: let it run them again (situation B), and know whether it does.
            if stopped and not await _start_again(hass, stopped):
                restart_needed = True
                reason = reason or "notstarted"
        except Exception:  # noqa: BLE001 - the original error is the one to report
            _LOGGER.exception("Putting the old names back after a failed move also failed. Restart Home Assistant: the snapshot "
                              "%s is kept, and at the next start it puts the old names back", SNAPSHOT_KEY)
            restart_needed, reason = True, "rollback"
        if isinstance(err, MoveFailure):
            err.restart = err.restart or restart_needed
            err.reason = reason or err.reason
            raise
        if isinstance(err, Exception):
            failure = MoveFailure(f"{type(err).__name__}: {err}")
            failure.restart = restart_needed
            failure.reason = reason
            raise failure from err
        raise
    # 6. what the moved installation needs from now on (none of it can undo the move, and none of it may raise)
    return await _finish_move(hass, store, snapshot, entries, steps, saved)


def _retag_one_device(hass: HomeAssistant, device: dr.DeviceEntry) -> None:
    identifiers = {_retag_identifier(identifier, OLD_DOMAIN, DOMAIN) for identifier in device.identifiers}
    dr.async_get(hass).async_update_device(device.id, new_identifiers=identifiers)


def _verify(hass: HomeAssistant, snapshot: dict) -> None:
    registry, devices = er.async_get(hass), dr.async_get(hass)
    if any(row.platform == OLD_DOMAIN for row in registry.entities.values()):
        raise MoveFailure("an entity is left under the old name")
    if any(_has_domain(d, OLD_DOMAIN) for d in devices.devices):
        raise MoveFailure("a device is left under the old name")
    if hass.config_entries.async_entries(OLD_DOMAIN):
        raise MoveFailure("a config entry is left under the old name")
    if len(snapshot["entities"]) != sum(1 for row in registry.entities.values() if row.platform == DOMAIN
                                         and row.entity_id in {e["entity_id"] for e in snapshot["entities"]}):
        raise MoveFailure("an entity of the snapshot is missing after the move")


# -- B2: a commit whose registries were not all written before the process ended ----------------------------------------
def _left_under_old_name(hass: HomeAssistant, doc: dict):
    """What of a completed move's snapshot is still under the old name: (rows, devices, entries, gone)."""
    registry, devices = er.async_get(hass), dr.async_get(hass)
    rows, gone = [], 0
    for item in doc.get("entities", []):
        row = registry.async_get(item["entity_id"])
        if row is None:
            gone += 1
        elif row.platform == OLD_DOMAIN:
            rows.append(row)
    old_devices = []
    for item in doc.get("devices", []):
        device = devices.async_get(item["id"])
        if device is None:
            gone += 1
        elif _has_domain(device, OLD_DOMAIN):
            old_devices.append(device)
    entries = [e for i in doc.get("entry_ids", []) if (e := hass.config_entries.async_get_entry(i)) is not None
               and e.domain == OLD_DOMAIN]
    return rows, old_devices, entries, gone


def _heal_blocker(hass: HomeAssistant, doc: dict, rows, old_devices, entries, gone: int) -> str | None:
    """Why the half state cannot be made consistent, or None."""
    if gone:
        return f"{gone} row(s) of the move's snapshot are no longer in the registries"
    registry, devices = er.async_get(hass), dr.async_get(hass)
    for row in rows:
        if registry.async_get_entity_id(row.domain, DOMAIN, row.unique_id) is not None:
            return f"an entity with unique id {row.unique_id} exists under both names"
    entry_ids = set(doc.get("entry_ids", []))
    for entry_id in sorted(entry_ids):
        for device in dr.async_entries_for_config_entry(devices, entry_id):
            if not _has_domain(device, OLD_DOMAIN):
                continue
            for identifier in device.identifiers:
                if _ident_domain(identifier) == OLD_DOMAIN and len(identifier) >= 2:
                    found = devices.async_get_device_by_identifier(_retag_identifier(identifier, OLD_DOMAIN, DOMAIN), entry_id)
                    if found is not None and found.id != device.id:
                        return f"a device with identifier {identifier[1]} exists under both names"
    for entry in entries:
        for other in hass.config_entries.async_entries(DOMAIN):
            if other.entry_id != entry.entry_id and entry.unique_id is not None and other.unique_id == entry.unique_id:
                return f"an installation under the new name already exists ({entry.unique_id})"
    return None


def _ensure_base(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """The move's base step, for an entry that the move's own write of it did not survive."""
    data = dict(entry.data)
    if not isinstance(data.get(CONF_TOPIC_PREFIX), str) or not data.get(CONF_TOPIC_PREFIX):
        hass.config_entries.async_update_entry(entry, data={**data, CONF_TOPIC_PREFIX: GATEWAY_TOPIC_PREFIX})


async def _heal_moved(hass: HomeAssistant, doc: dict) -> tuple[str | None, list[str]]:
    """The snapshot says moved. Home Assistant saves the config entries one second after a change and the registries ten
    seconds after (helpers/registry.py SAVE_DELAY), but the snapshot at once: a power cut in between leaves the snapshot
    saying moved with rows, devices or entries still under the old name, and the new code would then make `_2` duplicates.
    Idempotent: what is under the old name goes under the new one (the move's own steps, for the snapshot's items only).
    Returns (problem, entry ids healed). A problem means nothing was changed and the platforms must not be set up."""
    rows, old_devices, entries, gone = _left_under_old_name(hass, doc)
    if not (rows or old_devices or entries):
        return None, []  # the ordinary start: nothing to do
    if problem := _heal_blocker(hass, doc, rows, old_devices, entries, gone):
        return problem, []
    for entry in entries:  # situation B: the old code may have started it in this run
        if entry.state in (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.UNLOAD_IN_PROGRESS):
            return f"the old installation {entry.title!r} is still starting", []
    running = [e.entry_id for e in entries
               if e.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY, ConfigEntryState.FAILED_UNLOAD)]
    try:
        await _unload_all(hass, running, [])  # the move's own bounded unload: it raises nothing but MoveFailure
    except MoveFailure as err:
        return f"the old installation could not be stopped ({err})", []
    await _homekit_forward_files(hass, doc)  # the keys the move carried must be under the new name (a bridge that is not loaded)
    rows, old_devices, entries, gone = _left_under_old_name(hass, doc)  # after the awaits
    try:
        _homekit_live(hass, doc)  # loaded bridges: no await from here to the end of the retag
        for device in old_devices:
            _retag_one_device(hass, device)
        for row in rows:
            _platform_of(hass, row, DOMAIN)
        for entry in entries:
            _ensure_base(hass, entry)
            _set_domain(hass, entry, DOMAIN)
        _drop_issues(hass, OLD_DOMAIN)
        stored = [e for e in (hass.config_entries.async_get_entry(i) for i in doc.get("entry_ids", [])) if e is not None]
        problem = _stored_form_problem(stored, DOMAIN)
    except Exception as err:  # noqa: BLE001 - the state is still idempotently healable at the next start
        _LOGGER.exception("Healing an interrupted move to Emthera failed")
        return f"{type(err).__name__}: {err}", []
    if problem:
        return problem, []
    _LOGGER.info("A move to Emthera was completed but not all of it was saved before Home Assistant stopped; put under the "
                 "new name now: %d entities, %d devices, %d config entries", len(rows), len(old_devices), len(entries))
    return None, [e.entry_id for e in entries]


# -- after the move: aliases, notice, the old code's leftovers --------------------------------------------------------
_TEXTS = {
    "en": {"title": "Emthera: your installation was moved",
           "plain": "Your installation now runs under the new name Emthera. Nothing was lost: your devices, entities, "
                    "history, settings and automations are the same.",
           "folder": " The old folder custom_components/open_thermostat is no longer used. Restart Home Assistant once more; "
                     "then the old integration can be removed: uninstall OpenThermostat in the Marketplace if you installed "
                     "it there, or delete that folder if you copied it by hand.",
           "apple": " One thing could not be kept: Apple Home will show the thermostats of this installation as new accessories, "
                    "so their rooms, scenes and automations in Apple Home must be set up again.",
           "failed_title": "Emthera: the move did not complete",
           "failed": "Emthera could not move your installation to its new name. Nothing was changed, and your installation "
                     "runs as before under its old name. You can try again under Settings → Devices & services → "
                     "Add integration → Emthera.",
           "notstarted": "Emthera could not move your installation and put everything back as it was, but the previous version did not start again. Nothing of yours was lost, and the heating keeps running on the device itself. Restart Home Assistant, then try again.",
           "rollback": "Emthera could not move your installation and could not put everything back either. The heating keeps running on the device itself. Restart Home Assistant: at its next start Emthera puts the old names back from its saved snapshot, and tells you if that does not work.",
           "unsaved": " Emthera could not save its record of the move to disk. Your installation runs under the new name; if Home Assistant restarts before that is fixed, Emthera finishes the move by itself at the next start.",
           "undo_unsaved": "Emthera undid the move, but could not save its record of the undo to disk. If Home Assistant restarts now, check under Settings → Devices & services that your installation still has the old name.",
           "restart": "Emthera could not move your installation to its new name, because the previous version did not stop "
                      "cleanly. Nothing of yours was changed or lost, and the heating keeps running on the device itself. "
                      "Restart Home Assistant, then try again under Settings → Devices & services → Add integration → Emthera.",
           "undo_stuck": "Emthera could not undo the move, because the integration did not stop cleanly. Nothing was changed. "
                         "Restart Home Assistant, then try again.",
           "undo_busy": "Emthera could not undo the move, because the integration is still starting or stopping. Nothing was "
                        "changed. Wait a minute, then try again.",
           "undo_failed": "Emthera could not undo the move. Nothing was changed: the installation stays under the name Emthera. "
                          "The log says why.",
           "undo_half": "Emthera could not finish the undo and could not take it back either. Restart Home Assistant: at its "
                        "next start the old names are put back from the saved snapshot.",
           "half": "Emthera found an installation that was moved only halfway (for example after a power cut) and could not "
                   "finish it by itself. Emthera is not started, so that nothing gets worse; the heating keeps running on the "
                   "device itself. Put back the Home Assistant backup you made before the move, or open an issue and add the log.",
           "failed_not_running": "Emthera could not move your installation to its new name. Nothing of yours was changed "
                                 "or lost, but the integration is NOT running now: the previous version's folder is gone "
                                 "and the move did not complete. Try again under Settings → Devices & services → "
                                 "Add integration → Emthera. If that fails too, install the previous version again: "
                                 "your installation is still there, as it was."},
    "nl": {"title": "Emthera: je installatie is verplaatst",
           "plain": "Je installatie draait nu onder de nieuwe naam Emthera. Er is niets verloren gegaan: je apparaten, "
                    "entiteiten, geschiedenis, instellingen en automatiseringen zijn dezelfde.",
           "folder": " De oude map custom_components/open_thermostat wordt niet meer gebruikt. Start Home Assistant nog "
                     "één keer opnieuw op; daarna kan de oude integratie weg: verwijder OpenThermostat in de Marketplace "
                     "als je hem daar hebt geïnstalleerd, of verwijder de map als je hem met de hand hebt gekopieerd.",
           "apple": " Eén ding kon niet bewaard blijven: in de Woning-app van Apple (Apple Home) verschijnen de thermostaten van deze installatie "
                    "als nieuwe accessoires, dus hun kamers, scènes en automatiseringen in die app moet je opnieuw instellen.",
           "failed_title": "Emthera: het verplaatsen is niet gelukt",
           "failed": "Emthera kon je installatie niet naar de nieuwe naam verplaatsen. Er is niets veranderd en je "
                     "installatie draait als voorheen onder de oude naam. Je kunt het opnieuw proberen via "
                     "Instellingen → Apparaten en diensten → Integratie toevoegen → Emthera.",
           "notstarted": "Emthera kon je installatie niet verplaatsen en heeft alles teruggezet zoals het was, maar de vorige versie startte niet opnieuw. Er is niets van jou verloren gegaan en de verwarming blijft op het apparaat zelf doorlopen. Start Home Assistant opnieuw op en probeer het daarna opnieuw.",
           "rollback": "Emthera kon je installatie niet verplaatsen en kon ook niet alles terugzetten. De verwarming blijft op het apparaat zelf doorlopen. Start Home Assistant opnieuw op: bij de volgende start zet Emthera de oude namen terug vanuit de bewaarde momentopname, en meldt het als dat niet lukt.",
           "unsaved": " Emthera kon zijn vastlegging van het verplaatsen niet naar de schijf schrijven. Je installatie draait onder de nieuwe naam; als Home Assistant opnieuw opstart voordat dat is opgelost, maakt Emthera het verplaatsen bij de volgende start zelf af.",
           "undo_unsaved": "Emthera heeft het verplaatsen ongedaan gemaakt, maar kon de vastlegging daarvan niet naar de schijf schrijven. Als Home Assistant nu opnieuw opstart, controleer dan onder Instellingen → Apparaten en diensten of je installatie nog de oude naam heeft.",
           "restart": "Emthera kon je installatie niet naar de nieuwe naam verplaatsen, omdat de vorige versie niet netjes "
                      "stopte. Er is niets van jou veranderd of verloren gegaan en de verwarming blijft op het apparaat zelf "
                      "doorlopen. Start Home Assistant opnieuw op en probeer het daarna opnieuw via Instellingen → Apparaten en "
                      "diensten → Integratie toevoegen → Emthera.",
           "undo_stuck": "Emthera kon het verplaatsen niet ongedaan maken, omdat de integratie niet netjes stopte. Er is niets "
                         "veranderd. Start Home Assistant opnieuw op en probeer het daarna opnieuw.",
           "undo_busy": "Emthera kon het verplaatsen niet ongedaan maken, omdat de integratie nog aan het starten of stoppen is. "
                        "Er is niets veranderd. Wacht een minuut en probeer het dan opnieuw.",
           "undo_failed": "Emthera kon het verplaatsen niet ongedaan maken. Er is niets veranderd: de installatie blijft onder "
                          "de naam Emthera. In het logboek staat waarom.",
           "undo_half": "Emthera kon het ongedaan maken niet afmaken en ook niet terugdraaien. Start Home Assistant opnieuw op: "
                        "bij de volgende start worden de oude namen teruggezet vanuit de bewaarde momentopname.",
           "half": "Emthera vond een installatie die maar half is verplaatst (bijvoorbeeld door een stroomstoring) en kon dat "
                   "niet zelf afmaken. Emthera wordt niet gestart, zodat er niets erger wordt; de verwarming blijft op het "
                   "apparaat zelf doorlopen. Zet de back-up van Home Assistant terug die je vóór het verplaatsen hebt gemaakt, "
                   "of open een issue en voeg het logboek toe.",
           "failed_not_running": "Emthera kon je installatie niet naar de nieuwe naam verplaatsen. Er is niets van jou "
                                 "veranderd of verloren gegaan, maar de integratie draait nu NIET: de map van de vorige "
                                 "versie is weg en het verplaatsen is niet gelukt. Probeer het opnieuw via Instellingen → "
                                 "Apparaten en diensten → Integratie toevoegen → Emthera. Lukt dat ook niet, installeer "
                                 "dan de vorige versie opnieuw: je installatie staat er nog, zoals ze was."},
}


def _text(hass: HomeAssistant) -> dict:
    return _TEXTS["nl" if str(getattr(hass.config, "language", "en")).startswith("nl") else "en"]


def _after_move(hass: HomeAssistant, snapshot: dict, result: MoveResult) -> bool:
    """Aliases on, the old code's leftovers cleared, the one notice shown. True when the snapshot's "told" changed."""
    _best_effort("the old action names", enable_aliases, hass, replace_old_code=True)
    _best_effort("clearing the old code's leftovers", _clear_old_code_leftovers, hass)
    _best_effort("removing Home Assistant's repair for the old name", _drop_not_found_repair, hass)
    _best_effort("the notice of an earlier failed attempt", _dismiss_failed_notice, hass)
    apple = bool((snapshot.get("homekit") or {}).get("not_carried"))  # a bridge whose ids could not be carried: say so
    if snapshot.get("told") and not apple and result.reason != "unsaved":
        return False

    def tell() -> None:
        from homeassistant.components import persistent_notification
        text = _text(hass)
        persistent_notification.async_create(hass, text["plain"] + (text["folder"] if result.old_folder else "") + (text["apple"] if apple else "")
                                             + (text["unsaved"] if result.reason == "unsaved" else ""),
                                             title=text["title"], notification_id=NOTICE_ID)
    if _best_effort("the notice", tell):
        snapshot["told"] = True
        return True
    return False


def _dismiss_failed_notice(hass: HomeAssistant) -> None:
    """The notice "the move did not complete" of an earlier attempt (1.4.7 used the same id) is not true any more."""
    from homeassistant.components import persistent_notification
    persistent_notification.async_dismiss(hass, f"{NOTICE_ID}_failed")


def _drop_not_found_repair(hass: HomeAssistant) -> None:
    """Home Assistant's own repair "Integration open_thermostat not found" (setup.py _async_setup_component) offers the fix
    "Remove previous configurations", which would delete the installation. After the move no entry has that name: it is stale."""
    ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, f"integration_not_found.{OLD_DOMAIN}")


def failed_text(hass: HomeAssistant) -> str:
    """What a failed move means for the user: with the previous version's folder still there the old code runs the
    installation as before; without it nothing of ours runs until the move succeeds (the registries are as they were)."""
    return _text(hass)["failed" if _old_folder(hass) else "failed_not_running"]


def notify_failed(hass: HomeAssistant, detail: str, restart: bool = False, half: bool = False, reason: str = "") -> None:
    from homeassistant.components import persistent_notification
    key = "half" if half else reason if reason in ("notstarted", "rollback") else "restart" if restart else ""
    persistent_notification.async_create(hass, _text(hass)[key] if key else failed_text(hass),
                                         title=_text(hass)["failed_title"], notification_id=f"{NOTICE_ID}_failed")


def _clear_old_code_leftovers(hass: HomeAssistant) -> None:
    """Situation B: the old code ran in this process. Its card modules and notifications are taken off the page; the
    rest of it (actions, websocket commands) goes at the next restart. Best effort: none of it matters for the data."""
    try:
        from homeassistant.components import frontend
        urls = getattr(hass.data.get(frontend.DATA_EXTRA_MODULE_URL), "urls", frozenset())
        for url in sorted(u for u in urls if str(u).startswith(f"/{OLD_DOMAIN}/")):
            frontend.remove_extra_js_url(hass, url)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("old card modules could not be removed", exc_info=True)
    try:
        from homeassistant.components import persistent_notification
        notes = persistent_notification._async_get_or_create_notifications(hass)  # noqa: SLF001
        for note_id in [n for n in list(notes) if str(n).startswith(OLD_DOMAIN)]:
            persistent_notification.async_dismiss(hass, note_id)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("old notifications could not be dismissed", exc_info=True)


# -- aliases ------------------------------------------------------------------------------------------------------
def aliases_wanted(hass: HomeAssistant) -> bool:
    return bool(hass.data.get(_ALIASES, {}).get("on"))


@callback
def enable_aliases(hass: HomeAssistant, *, replace_old_code: bool = False) -> None:
    """The old action names call the new ones (automations and scripts of the old name keep working).

    replace_old_code: right after a move in situation B the old code is still loaded in this run and its actions are still
    registered under the old name; they belong to entries that no longer exist, so they are taken away first."""
    state = hass.data.setdefault(_ALIASES, {})
    if state.get("on"):
        return
    state["on"] = True
    if replace_old_code:
        for name in list(hass.services.async_services_for_domain(OLD_DOMAIN)):
            hass.services.async_remove(OLD_DOMAIN, name)
    for name in list(hass.services.async_services_for_domain(DOMAIN)):
        _register_alias(hass, name)

    @callback
    def registered(event) -> None:
        if event.data.get("domain") == DOMAIN:
            _register_alias(hass, event.data["service"])

    @callback
    def removed(event) -> None:
        if event.data.get("domain") == DOMAIN and event.data.get("service") != UNDO_SERVICE:
            hass.services.async_remove(OLD_DOMAIN, event.data["service"])

    state["unsub"] = [hass.bus.async_listen("service_registered", registered),
                      hass.bus.async_listen("service_removed", removed)]


@callback
def disable_aliases(hass: HomeAssistant) -> None:
    state = hass.data.get(_ALIASES) or {}
    for unsub in state.pop("unsub", []):
        unsub()
    if state.pop("on", None):
        for name in list(hass.services.async_services_for_domain(OLD_DOMAIN)):
            hass.services.async_remove(OLD_DOMAIN, name)


def _register_alias(hass: HomeAssistant, name: str) -> None:
    if name == UNDO_SERVICE or hass.services.has_service(OLD_DOMAIN, name):
        return
    supports = hass.services.supports_response(DOMAIN, name)

    async def handler(call: ServiceCall):
        return await hass.services.async_call(DOMAIN, name, dict(call.data), blocking=True, context=call.context,
                                              return_response=bool(call.return_response))

    hass.services.async_register(OLD_DOMAIN, name, handler, schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
                                 supports_response=supports if isinstance(supports, SupportsResponse) else SupportsResponse.NONE)
    # The old name is not an integration with a services.yaml: its description is given here, so that Home Assistant does not
    # log a failed services.yaml load for it every time the frontend asks for the descriptions.
    from homeassistant.helpers.service import async_set_service_schema
    async_set_service_schema(hass, OLD_DOMAIN, name, {
        "name": f"{name} (old name)", "description": f"The old name of {DOMAIN}.{name}: the same action. Use {DOMAIN}.{name} in new automations.",
        "fields": {}})


def fire_event(hass: HomeAssistant, name: str, data: dict) -> None:
    """The notification event under its new name, and under the old one while the aliases are on."""
    hass.bus.async_fire(name, data)
    if aliases_wanted(hass) and name == f"{DOMAIN}_notification":
        hass.bus.async_fire(OLD_EVENT, data)


# -- the way back -------------------------------------------------------------------------------------------------
async def async_undo(hass: HomeAssistant) -> MoveResult:
    """Put the old names back (the action emthera.undo_move). Stored files are not touched: the old ones were never changed."""
    async with _lock(hass):
        store = _store(hass)
        doc = await store.async_load()
        if not isinstance(doc, dict) or doc.get("status") != MOVED:
            return MoveResult("no_snapshot", detail="there is no completed move to undo")
        entry_ids = set(doc.get("entry_ids", []))
        text = _text(hass)
        entries = [e for e in (hass.config_entries.async_get_entry(i) for i in sorted(entry_ids)) if e is not None]
        # Before anything changes: Home Assistant refuses to unload an entry in a failed stop, and one that is starting or
        # stopping right now is not touched either (config_entries.py async_unload: the state is not recoverable).
        if any(e.state is ConfigEntryState.FAILED_UNLOAD for e in entries):
            return MoveResult("failed", detail=text["undo_stuck"], reason="restart")
        if any(e.state in (ConfigEntryState.SETUP_IN_PROGRESS, ConfigEntryState.UNLOAD_IN_PROGRESS) for e in entries):
            return MoveResult("failed", detail=text["undo_busy"])
        running = [e.entry_id for e in entries if e.state not in (ConfigEntryState.NOT_LOADED, ConfigEntryState.SETUP_ERROR,
                                                                  ConfigEntryState.MIGRATION_ERROR)]
        stopped: list[str] = []
        try:
            await _unload_all(hass, running, stopped)
        except MoveFailure as err:
            again = await _start_again(hass, stopped)
            restart = err.restart or not again
            return MoveResult("failed", detail=text["undo_stuck" if restart else "undo_failed"], reason="restart" if restart else "")
        disable_aliases(hass)
        data_before = {e.entry_id: dict(e.data) for e in entries}
        await _homekit_back_files(hass, doc)  # the keys of the bridges that are not loaded first; the loaded ones go back inside the restore
        try:
            problem = _restore_registries(hass, doc, entry_ids=entry_ids, drop_new_issues=True)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("The undo of the move stopped halfway")
            problem = "the registries could not be put back"
        if problem:
            if _reapply_move(hass, doc, entry_ids, data_before):  # nothing is put back: the installation is as it was
                await _homekit_forward_files(hass, doc)
                _best_effort("the old action names", enable_aliases, hass)
                again = await _start_again(hass, stopped)
                return MoveResult("failed", detail=text["undo_failed" if again else "undo_stuck"], reason="" if again else "restart")
            # Neither forward nor back: the snapshot must not say moved. In progress is what the next start puts back.
            doc.update(status=IN_PROGRESS, interrupted="undo", detail="the undo stopped halfway; restored at the next start")
            await store.async_save(doc)
            return MoveResult("failed", detail=text["undo_half"], reason="restart")
        doc.update(status=UNDONE, undone=dt_util.utcnow().isoformat())
        await store.async_save(doc)
        if not await _saved_status(hass, UNDONE):
            _best_effort("the notice that the undo was not saved", _tell_undo_unsaved, hass)
            return MoveResult("undone", entries=len(entry_ids), reason="unsaved", detail=text["undo_unsaved"])
        return MoveResult("undone", entries=len(entry_ids))


def _tell_undo_unsaved(hass: HomeAssistant) -> None:
    from homeassistant.components import persistent_notification
    persistent_notification.async_create(hass, _text(hass)["undo_unsaved"], title=_text(hass)["failed_title"],
                                         notification_id=f"{NOTICE_ID}_undo")


def _reapply_move(hass: HomeAssistant, snapshot: dict, entry_ids: set[str], data_before: dict[str, dict]) -> bool:
    """An undo that stopped halfway: the moved state again (synchronous and idempotent, like the restore). True when it holds."""
    try:
        _homekit_live(hass, snapshot)  # the keys of the loaded bridges first, in the same synchronous stretch as the rows
        for entry_id in entry_ids:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            if entry_id in data_before and dict(entry.data) != data_before[entry_id]:
                hass.config_entries.async_update_entry(entry, data=data_before[entry_id])
            _set_domain(hass, entry, DOMAIN)
        _retag_devices(hass, OLD_DOMAIN, DOMAIN, entry_ids)
        _retag_entities(hass, OLD_DOMAIN, DOMAIN, entry_ids, also={e["entity_id"] for e in snapshot.get("entities", [])})
        _drop_issues(hass, OLD_DOMAIN)
        problem = _stored_form_problem([e for e in (hass.config_entries.async_get_entry(i) for i in entry_ids) if e is not None], DOMAIN)
        if problem:
            _LOGGER.error("After taking the undo back: %s", problem)
        return problem is None
    except Exception:  # noqa: BLE001
        _LOGGER.exception("The undo stopped halfway and could not be taken back")
        return False


# -- start of the integration (async_setup) ---------------------------------------------------------------------------
async def async_start(hass: HomeAssistant) -> bool:
    """Domain level, once per run: the undo action, the recovery of an interrupted move, the aliases of a moved one.

    Home Assistant awaits the integration's async_setup before it sets up any of its config entries and their platforms
    (homeassistant/setup.py: `result = await task` at 408-418, the entries at 463-475), and does not set them up at all
    when async_setup returns False (440-442). So everything here is finished before any entity of ours can be created.
    False: the state of an earlier move cannot be made consistent; the caller must return False from async_setup."""
    if not hass.services.has_service(DOMAIN, UNDO_SERVICE):
        async def undo(call: ServiceCall) -> None:
            result = await async_undo(hass)
            if result.status != "undone":
                raise ServiceValidationError(result.detail or "nothing to undo")
        from homeassistant.helpers.service import async_register_admin_service
        async_register_admin_service(hass, DOMAIN, UNDO_SERVICE, undo, schema=vol.Schema({}))
    async with _lock(hass):
        try:
            doc = await _store(hass).async_load()
            doc = doc if isinstance(doc, dict) else None
            if kind := await _recover(hass, doc):
                _after_recovery(hass, doc, kind)
            hass.data[_RECOVERED] = True
            problem = None
            if doc and doc.get("status") == MOVED:
                problem, _ = await _heal_moved(hass, doc)
        except Exception as err:  # noqa: BLE001 - never out of async_setup: the half notification and False
            _LOGGER.exception("The state of an earlier move to Emthera could not be put right")
            hass.data[_RECOVERED] = True
            problem = f"{type(err).__name__}: {err}"
        if problem:
            _LOGGER.error("The move to Emthera is not consistent and cannot be completed by itself: %s", problem)
            notify_failed(hass, problem, half=True)
            return False
        if doc and doc.get("status") == MOVED:
            enable_aliases(hass)
    return True


def automatic_allowed(hass: HomeAssistant) -> bool:
    """The MQTT trigger asks once per run, and never after a failed or undone move (that is the user's to retry)."""
    if hass.data.get(_ATTEMPTED):
        return False
    hass.data[_ATTEMPTED] = True
    return True


async def async_auto_move(hass: HomeAssistant) -> None:
    doc = await load_snapshot(hass)
    if doc and doc.get("status") == UNDONE:
        return
    if doc and doc.get("status") == FAILED:
        # A failed move is the user's to retry, except the one automatic retry of an interrupted move or of files that kept
        # changing (the old code was still saving) - and the snapshot the published 1.4.7 left (it knows neither key): once.
        left_by_147 = "retry" not in doc and "auto_retried" not in doc
        if not (doc.get("retry") or left_by_147):
            return
        doc.update(retry=False, auto_retried=True)
        await _store(hass).async_save(doc)
    result = await async_move(hass, "mqtt")
    if result.status in ("failed", "blocked"):
        notify_failed(hass, result.detail, result.reason == "restart", result.reason == "half", result.reason)
