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

IN_PROGRESS, MOVED, FAILED, UNDONE = "in_progress", "moved", "failed", "undone"
STEPS = ("stop", "snapshot", "files", "base", "devices", "entities", "entries", "issues", "commit")

_LOCK = f"{DOMAIN}_move_lock"
_ATTEMPTED = f"{DOMAIN}_move_attempted"
_ALIASES = f"{DOMAIN}_move_aliases"
_inject: tuple[str, int] | None = None  # tests only: raise before item N of a step (N = items done so far)


class MoveFailure(Exception):
    """A step failed; the installation is put back as it was."""


@dataclass
class MoveResult:
    status: str  # moved | nothing | blocked | failed | undone | no_snapshot
    entries: int = 0
    detail: str = ""
    old_folder: bool = False
    steps: list[str] = field(default_factory=list)
    to_setup: list[str] = field(default_factory=list)


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
            "data": _plain(issue.data), "dismissed_version": issue.dismissed_version}


def _collect(hass: HomeAssistant, entries: list[ConfigEntry]) -> dict:
    ids = {entry.entry_id for entry in entries}
    entities = [{"entity_id": row.entity_id, "platform": row.platform, "unique_id": row.unique_id,
                 "config_entry_id": row.config_entry_id, "config_subentry_id": row.config_subentry_id,
                 "device_id": row.device_id, "name": row.name, "area_id": row.area_id,
                 "disabled_by": str(row.disabled_by) if row.disabled_by else None,
                 "hidden_by": str(row.hidden_by) if row.hidden_by else None}
                for row in er.async_get(hass).entities.values() if row.platform == OLD_DOMAIN]
    devices = [{"id": device.id, "identifiers": sorted(list(i) for i in device.identifiers),
                "name": device.name, "name_by_user": device.name_by_user, "area_id": device.area_id}
               for device in _devices_of(hass, ids) if any(domain == OLD_DOMAIN for domain, _ in device.identifiers)]
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
            for domain, ident in device.identifiers:
                if domain == OLD_DOMAIN and devices.async_get_device_by_identifier((DOMAIN, ident), entry.entry_id) is not None:
                    return f"a device with identifier {ident} already exists under the new name"
    registry = er.async_get(hass)
    for row in list(registry.entities.values()):
        if row.platform == OLD_DOMAIN and registry.async_get_entity_id(row.domain, DOMAIN, row.unique_id) is not None:
            return f"an entity with unique id {row.unique_id} already exists under the new name"
    return None


# -- files (blocking; run in the executor) ------------------------------------------------------------------------
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _list_old_files(config_dir: Path) -> dict:
    storage = config_dir / ".storage"
    files = []
    if storage.is_dir():
        for path in sorted(storage.iterdir()):
            if path.is_file() and (path.name.startswith(OLD_DOMAIN + ".") or path.name.startswith(OLD_DOMAIN + "_")):
                files.append({"name": path.name, "sha256": _sha(path), "size": path.stat().st_size})
    tester = config_dir / f"{OLD_DOMAIN}_tester"
    folder = []
    if tester.is_dir():
        folder = [{"name": p.name, "sha256": _sha(p), "size": p.stat().st_size} for p in sorted(tester.iterdir()) if p.is_file()]
    return {"storage": files, "tester": folder}


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
            raise MoveFailure(f"{item['name']} changed while it was copied")
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = None
        items.append({"name": item["name"], "doc": doc, "private": (src.stat().st_mode & 0o077) == 0})
    return items


def _json_or_none(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _set_aside(path: Path) -> None:
    """A file of the new name that differs (an earlier move that was undone, then the old version ran on): the old files
    are the current ones; the other file stays beside it, never lost."""
    backup = path.with_name(path.name + ".replaced")
    n = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.replaced{n}")
        n += 1
    os.replace(path, backup)


async def _copy_storage(hass: HomeAssistant, config_dir: Path, listing: dict, created: list[str]) -> dict:
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
            await hass.async_add_executor_job(_set_aside, dst)
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
                raise MoveFailure(f"{item['name']} changed while it was copied")
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
    return now == listing


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


# -- the registries (synchronous: nothing else runs while they change) ---------------------------------------------
_RESET = ("supports_unload", "supports_remove_device", "_supports_options", "_supports_reconfigure",
          "_supported_subentry_types", "_integration_for_domain")


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
        if not any(domain == frm for domain, _ in device.identifiers):
            continue
        identifiers = {(to if domain == frm else domain, ident) for domain, ident in device.identifiers}
        devices.async_update_device(device.id, new_identifiers=identifiers)
        count += 1
    return count


def _retag_entities(hass: HomeAssistant, frm: str, to: str, entry_ids: set[str] | None = None) -> int:
    registry = er.async_get(hass)
    count = 0
    for row in list(registry.entities.values()):
        if row.platform != frm:
            continue
        if entry_ids is not None and row.config_entry_id not in entry_ids:
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


def _recreate_issues(hass: HomeAssistant, documents: list[dict]) -> None:
    for doc in documents:
        severity = str(doc.get("severity", "warning")).rsplit(".", 1)[-1].lower()
        ir.async_create_issue(
            hass, OLD_DOMAIN, doc["issue_id"], is_fixable=bool(doc.get("is_fixable")),
            is_persistent=bool(doc.get("is_persistent")), severity=ir.IssueSeverity(severity),
            translation_key=doc.get("translation_key"), translation_placeholders=doc.get("translation_placeholders"),
            learn_more_url=doc.get("learn_more_url"), data=doc.get("data"))
        if doc.get("dismissed_version"):
            ir.async_ignore_issue(hass, OLD_DOMAIN, doc["issue_id"], True)


def _restore_registries(hass: HomeAssistant, snapshot: dict, *, entry_ids: set[str], drop_new_issues: bool = False) -> None:
    """Everything back to the old name. Idempotent: it sets the old state whatever part of the move happened."""
    originals = {doc["entry_id"]: doc for doc in snapshot.get("entries", [])}
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            continue
        original = originals.get(entry_id)
        if original is not None and dict(entry.data) != original["data"] and entry.domain == OLD_DOMAIN:
            hass.config_entries.async_update_entry(entry, data=original["data"])
        _set_domain(hass, entry, OLD_DOMAIN)
    _retag_entities(hass, DOMAIN, OLD_DOMAIN, entry_ids)
    _retag_devices(hass, DOMAIN, OLD_DOMAIN, entry_ids)
    if drop_new_issues:
        _drop_issues(hass, DOMAIN)
    have = {issue_id for (domain, issue_id) in ir.async_get(hass).issues if domain == OLD_DOMAIN}
    _recreate_issues(hass, [d for d in snapshot.get("issues", []) if d["issue_id"] not in have])


# -- the move -----------------------------------------------------------------------------------------------------
def _lock(hass: HomeAssistant) -> asyncio.Lock:
    return hass.data.setdefault(_LOCK, asyncio.Lock())


async def async_move(hass: HomeAssistant, trigger: str = "user") -> MoveResult:
    """Move every installation of the old name. Safe to call at any time and from several places at once."""
    async with _lock(hass):
        try:
            result = await _move(hass, trigger)
        except MoveFailure as err:
            _LOGGER.error("The move to Emthera did not complete and was undone: %s", err)
            return MoveResult("failed", detail=str(err))
    # Outside the lock: setting up the integration runs its async_setup, which takes the same lock.
    for entry_id in result.to_setup:
        try:
            await hass.config_entries.async_setup(entry_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("The moved installation %s could not be set up", entry_id)
    return result


async def _recover(hass: HomeAssistant, doc: dict | None) -> None:
    """A snapshot that still says in_progress: Home Assistant stopped during a move; put everything back first."""
    if doc and doc.get("status") == IN_PROGRESS:
        _LOGGER.warning("An earlier move to Emthera was interrupted; putting the old names back first")
        _restore_registries(hass, doc, entry_ids=set(doc.get("entry_ids", [])))
        doc["status"], doc["detail"] = FAILED, "interrupted; restored at the next start"
        await _store(hass).async_save(doc)


async def _move(hass: HomeAssistant, trigger: str) -> MoveResult:
    store = _store(hass)
    previous = await store.async_load()
    await _recover(hass, previous if isinstance(previous, dict) else None)
    entries = old_entries(hass)
    if not entries:
        return MoveResult("nothing")
    config_dir = Path(hass.config.path())
    steps: list[str] = []
    created: list[str] = []
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
        was_loaded = [entry.entry_id for entry in entries
                      if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY, ConfigEntryState.FAILED_UNLOAD)]
        for entry_id in was_loaded:
            if not await hass.config_entries.async_unload(entry_id):
                raise MoveFailure(f"the old installation {hass.config_entries.async_get_entry(entry_id).title!r} could not be stopped")
            stopped.append(entry_id)
        steps.append("stop")
        # 2. the snapshot, written and read back before any registry or file of ours changes
        _checkpoint("snapshot")
        listing = await hass.async_add_executor_job(_list_old_files, config_dir)
        snapshot = {"schema": 1, "status": IN_PROGRESS, "taken": dt_util.utcnow().isoformat(), "trigger": trigger,
                    "from": OLD_DOMAIN, "to": DOMAIN, **_collect(hass, entries), "files": listing, "was_loaded": was_loaded,
                    "told": bool(isinstance(previous, dict) and previous.get("told"))}
        await store.async_save(snapshot)
        if await _store(hass).async_load() != snapshot:
            raise MoveFailure("the snapshot could not be read back")
        steps.append("snapshot")
        # 3. the stored files, copied and compared
        _checkpoint("files")
        copied = await _copy_storage(hass, config_dir, listing, created)
        tester = await hass.async_add_executor_job(_copy_tester, config_dir, listing, created)
        copied = {key: copied[key] + tester[key] for key in copied}
        if not await hass.async_add_executor_job(_old_files_unchanged, config_dir, listing):
            raise MoveFailure("an old stored file changed during the move")
        steps.append("files")
        # 4. the registries: no await from here until the end of step 8
        _checkpoint("base")
        for entry in entries:
            data = dict(entry.data)
            if not isinstance(data.get(CONF_TOPIC_PREFIX), str) or not data.get(CONF_TOPIC_PREFIX):
                hass.config_entries.async_update_entry(entry, data={**data, CONF_TOPIC_PREFIX: GATEWAY_TOPIC_PREFIX})
        steps.append("base")
        _checkpoint("devices")
        for n, device in enumerate([d for d in _devices_of(hass, entry_ids)
                                    if any(dom == OLD_DOMAIN for dom, _ in d.identifiers)]):
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
    except BaseException as err:
        # Back to the old names (synchronously, whatever the error: also a cancelled task must not leave half a move).
        try:
            _restore_registries(hass, snapshot or {"entries": [], "issues": []}, entry_ids=entry_ids)
            await hass.async_add_executor_job(_remove_created, config_dir, created)
            if snapshot:
                snapshot.update(status=FAILED, detail=str(err) or type(err).__name__, steps=steps)
                await _store(hass).async_save(snapshot)
            for entry_id in stopped:  # the old code ran them: let it run them again (situation B)
                hass.async_create_task(hass.config_entries.async_setup(entry_id))
        except Exception:  # noqa: BLE001 - the original error is the one to report
            _LOGGER.exception("Putting the old names back after a failed move also failed; use emthera.undo_move")
        if isinstance(err, MoveFailure):
            raise
        if isinstance(err, Exception):
            raise MoveFailure(f"{type(err).__name__}: {err}") from err
        raise
    # 6. what the moved installation needs from now on (none of it can undo the move)
    result = MoveResult("moved", entries=len(entries), old_folder=_old_folder(hass), steps=steps)
    if _after_move(hass, snapshot, result):
        await store.async_save(snapshot)
    result.to_setup = [entry.entry_id for entry in entries if entry.disabled_by is None]
    return result


def _retag_one_device(hass: HomeAssistant, device: dr.DeviceEntry) -> None:
    identifiers = {(DOMAIN if domain == OLD_DOMAIN else domain, ident) for domain, ident in device.identifiers}
    dr.async_get(hass).async_update_device(device.id, new_identifiers=identifiers)


def _verify(hass: HomeAssistant, snapshot: dict) -> None:
    registry, devices = er.async_get(hass), dr.async_get(hass)
    if any(row.platform == OLD_DOMAIN for row in registry.entities.values()):
        raise MoveFailure("an entity is left under the old name")
    if any(dom == OLD_DOMAIN for d in devices.devices for dom, _ in d.identifiers):
        raise MoveFailure("a device is left under the old name")
    if hass.config_entries.async_entries(OLD_DOMAIN):
        raise MoveFailure("a config entry is left under the old name")
    if len(snapshot["entities"]) != sum(1 for row in registry.entities.values() if row.platform == DOMAIN
                                         and row.entity_id in {e["entity_id"] for e in snapshot["entities"]}):
        raise MoveFailure("an entity of the snapshot is missing after the move")


# -- after the move: aliases, notice, the old code's leftovers --------------------------------------------------------
_TEXTS = {
    "en": {"title": "Emthera: your installation was moved",
           "plain": "Your installation now runs under the new name Emthera. Nothing was lost: your devices, entities, "
                    "history, settings and automations are the same.",
           "folder": " The old folder custom_components/open_thermostat is no longer used. Restart Home Assistant once more; "
                     "then the old integration can be removed: uninstall OpenThermostat in the Marketplace if you installed "
                     "it there, or delete that folder if you copied it by hand.",
           "failed_title": "Emthera: the move did not complete",
           "failed": "Emthera could not move your installation to its new name. Nothing was changed, and your installation "
                     "runs as before under its old name. You can try again under Settings → Devices & services → "
                     "Add integration → Emthera.",
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
           "failed_title": "Emthera: het verplaatsen is niet gelukt",
           "failed": "Emthera kon je installatie niet naar de nieuwe naam verplaatsen. Er is niets veranderd en je "
                     "installatie draait als voorheen onder de oude naam. Je kunt het opnieuw proberen via "
                     "Instellingen → Apparaten en diensten → Integratie toevoegen → Emthera.",
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
    enable_aliases(hass, replace_old_code=True)
    _clear_old_code_leftovers(hass)
    if not snapshot.get("told"):
        from homeassistant.components import persistent_notification
        text = _text(hass)
        persistent_notification.async_create(hass, text["plain"] + (text["folder"] if result.old_folder else ""),
                                             title=text["title"], notification_id=NOTICE_ID)
        snapshot["told"] = True
        return True
    return False


def failed_text(hass: HomeAssistant) -> str:
    """What a failed move means for the user: with the previous version's folder still there the old code runs the
    installation as before; without it nothing of ours runs until the move succeeds (the registries are as they were)."""
    return _text(hass)["failed" if _old_folder(hass) else "failed_not_running"]


def notify_failed(hass: HomeAssistant, detail: str) -> None:
    from homeassistant.components import persistent_notification
    persistent_notification.async_create(hass, failed_text(hass), title=_text(hass)["failed_title"],
                                         notification_id=f"{NOTICE_ID}_failed")


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
        for entry_id in entry_ids:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.state not in (ConfigEntryState.NOT_LOADED, ConfigEntryState.SETUP_ERROR,
                                                          ConfigEntryState.MIGRATION_ERROR, ConfigEntryState.FAILED_UNLOAD):
                if not await hass.config_entries.async_unload(entry_id):
                    return MoveResult("failed", detail=f"{entry.title!r} could not be stopped")
        disable_aliases(hass)
        _restore_registries(hass, doc, entry_ids=entry_ids, drop_new_issues=True)
        doc.update(status=UNDONE, undone=dt_util.utcnow().isoformat())
        await store.async_save(doc)
        return MoveResult("undone", entries=len(entry_ids))


# -- start of the integration (async_setup) ---------------------------------------------------------------------------
async def async_start(hass: HomeAssistant) -> None:
    """Domain level, once per run: the undo action, the recovery of an interrupted move, the aliases of a moved one."""
    if not hass.services.has_service(DOMAIN, UNDO_SERVICE):
        async def undo(call: ServiceCall) -> None:
            result = await async_undo(hass)
            if result.status != "undone":
                raise ServiceValidationError(result.detail or "nothing to undo")
        from homeassistant.helpers.service import async_register_admin_service
        async_register_admin_service(hass, DOMAIN, UNDO_SERVICE, undo, schema=vol.Schema({}))
    async with _lock(hass):
        doc = await _store(hass).async_load()
        doc = doc if isinstance(doc, dict) else None
        await _recover(hass, doc)
        if doc and doc.get("status") == MOVED:
            enable_aliases(hass)


def automatic_allowed(hass: HomeAssistant) -> bool:
    """The MQTT trigger asks once per run, and never after a failed or undone move (that is the user's to retry)."""
    if hass.data.get(_ATTEMPTED):
        return False
    hass.data[_ATTEMPTED] = True
    return True


async def async_auto_move(hass: HomeAssistant) -> None:
    doc = await load_snapshot(hass)
    if doc and doc.get("status") in (UNDONE, FAILED):
        return
    result = await async_move(hass, "mqtt")
    if result.status in ("failed", "blocked"):
        notify_failed(hass, result.detail)
