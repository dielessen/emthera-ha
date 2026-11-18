"""Firmware updates of the device through Home Assistant, like ESPHome.

Home Assistant reads the product's signed update list (update_catalog.py: https://updates.emthera.nl/v1/, the update
route of docs/engineering/UPDATE-ROUTE.md), downloads the chosen file, verifies it completely (the list's size and
SHA-256, then the file's own signed trailer, then the binding between the two) and uploads it to the device over the
local network (/ota, the same route as the device's update page). The device itself makes no HTTPS connection here.
Credentials are the ones stored by the controller connection step. The offers come from that list only (the entity, its ids
and its install route are the ones of earlier releases).

Which firmware: the product follows the board the device reports in /status (``bbqkees_e32v2`` is the old gateway,
``emthera_hub_v1`` the Hub); a device that reports no board is the old gateway. A Hub never receives a gateway
file and the other way round (the list is chosen by product, the trailer is checked against the device's board, layout
and settings schema).

Tags: pre-releases such as ``v0.1.0-e32v2-beta.18`` or ``v1.1.0-hub-beta.1`` (alpha < beta < rc) and stable releases
such as ``v1.0.0-e32v2``; a stable release is newer than its release candidates. An installation is never offered a
less mature channel than the one it runs (the specification's rule): 1.0.0 is not offered 1.1.0-beta.1.

A list that is old, unreachable or not verifiable offers nothing: the installed version stays shown as the latest, one
short sentence says what is the matter (``release_summary``), the attributes ``catalog_status``, ``catalog_reason``,
``catalog_generation`` and ``last_checked`` say it for automations, and nothing becomes Unavailable or Unknown. No
Repair is raised for it (decision D8: Repairs are for faults in the installation).

The entity keeps a record of its last install (attribute ``last_install``:
release, SHA-256, size, start, end, duration, result and the identity the E32
reports after its restart; never an address or a password). It is the Home
Assistant side of an update acceptance (docs/modern-thermostat/HA-UPDATE-ACCEPTANCE.en.md).

1.4.2 (HA-REREAD, plan 3.2): after a confirmed install the entity asks the room-plan link to read the E32's
abilities again (``_abilities_read_again`` → ``RoomPlanLink.request_refresh``), and it observes every such read
(``HeatingHub.add_firmware_listener``): an E32 that restarted on other firmware (installed from its own page, by
another Home Assistant, a downgrade) shows its version at once, not at the next six-hourly read (review HC-16).

1.4.2 (HA-SESSIONS, plan 3.16, review HC-10): every sign-in of this entity (the version read, the upload and the
confirmation every 5 s after it) passes the integration's session gate (controller_link.SessionGate: at most two
E32 web sessions of Home Assistant at once), so a browser on the E32's own pages keeps its sessions during an
update. Since a restart's version reaches the entity through that observer, the scheduled check signs in to the
E32 for its version only once a day (VERSION_READ_INTERVAL); the update list is asked every six hours. The read at
start-up and the retries after a failed read always go to the E32.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import logging
import re
import time

import aiohttp
from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import update_catalog as catalog
from .const import CONF_TOPIC_PREFIX, DOMAIN
from .controller_link import (ControllerClient, ControllerLinkError, ControllerLoginRejected, SESSION_WAITS,
                              async_login_waiting)
from .controller_setup_flow import CONTROLLER_ADDRESS, CONTROLLER_PASSWORD

_LOGGER = logging.getLogger(__name__)
CHECK_INTERVAL = timedelta(hours=6)
# The scheduled check reads the version from the E32 only when no read (its own, or the room-plan link's after an
# E32 restart) confirmed it for this long; the half hour keeps a six-hourly tick from just missing the day.
VERSION_READ_INTERVAL = timedelta(hours=24)
VERSION_READ_SLACK = timedelta(minutes=30)
# After a failed read of the installed version (E32 restarting, unreachable, all
# its web sessions in use, ...): try again after 1, 5 and 15 minutes, then the
# normal interval. A known version is kept meanwhile.
RETRY_DELAYS = (60, 300, 900)
_NUMBER = r"(0|[1-9]\d{0,8})"
TAG = re.compile(rf"v{_NUMBER}\.{_NUMBER}\.{_NUMBER}-(?:e32v2|hub)(?:-(alpha|beta|rc)\.{_NUMBER})?")
# The real size of the OTA slot of each product: the gateway's smaller slot is 3,670,016 bytes (it was 0x3C0000 until
# 1.4.6), the Hub's slots (layout v2) are 3,932,160 bytes.
MAX_IMAGE = {"e32v2": 0x380000, "hub": 0x3C0000}


def max_image_for_tag(tag):
    """The slot size of the product a release tag belongs to (``-hub`` tags: the Hub, everything else: the gateway)."""
    return MAX_IMAGE["hub"] if isinstance(tag, str) and re.search(r"-hub(?:-|$)", tag) else MAX_IMAGE["e32v2"]
CHANNELS = {"alpha": 0, "beta": 1, "rc": 2, None: 3}
STABLE = CHANNELS[None]
# last_install["result"]: how the last install started from Home Assistant ended.
RESULTS = ("installed", "download_failed", "verification_failed", "upload_failed", "not_confirmed")
INSTALL_RECORD = ("tag", "from_version", "sha256", "size", "started_at", "finished_at", "duration_s",
                  "result", "uploads", "reported")
# Added with the update list on the website (additive: a record of an earlier version has neither and stays valid):
# the generation of the list the file came from, and the key slot (0 or 1) that signed the file.
INSTALL_RECORD_EXTRA = ("catalog_generation", "key_slot")
# The board a device reports in /status -> the product of the update list. No board = the old gateway.
BOARD_PRODUCTS = {"bbqkees_e32v2": "e32v2", "emthera_hub_v1": "hub"}
STORE_KEY = f"{DOMAIN}.update_list"
CATALOG_KEY = f"{DOMAIN}_update_catalog"  # hass.data: the one client of the installation
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# Where a failed install stopped (last_install "result") -> the error Home Assistant shows, in the user's
# language (exceptions.<key>), instead of "Unknown error".
INSTALL_ERRORS = {"download_failed": "firmware_download_failed", "verification_failed": "firmware_verification_failed",
                  "upload_failed": "firmware_upload_failed", "not_confirmed": "firmware_not_confirmed"}


class _InstallFailed(Exception):
    """The install stopped where last_install's result says."""


def install_error(result, error=None):
    """The translated Home Assistant error for an install that stopped at ``result``."""
    return HomeAssistantError(translation_domain=DOMAIN, translation_key=INSTALL_ERRORS[result],
                              translation_placeholders={"error": error or "-"} if result == "upload_failed" else None)


def parse_tag(tag):
    """(major, minor, patch, channel rank, number) or None for a foreign tag.

    Channel rank: alpha 0, beta 1, rc 2, stable 3 (number 0).
    """
    match = TAG.fullmatch(tag) if isinstance(tag, str) else None
    if not match:
        return None
    major, minor, patch, channel, number = match.groups()
    return int(major), int(minor), int(patch), CHANNELS[channel], int(number or 0)


def is_stable(tag):
    key = parse_tag(tag)
    return key is not None and key[3] == STABLE


def utc_text(moment):
    return dt_util.as_utc(moment).strftime("%Y-%m-%dT%H:%M:%SZ")


def reported_identity(version):
    """The identity the E32 reports in /status/version (nothing else it sends)."""
    if not isinstance(version, dict) or parse_tag(version.get("version")) is None:
        return None
    identity = {"version": version["version"]}
    for key, field, length in (("source_commit", "source", 40), ("web_sha256", "web_sha256", 64),
                               ("elf_sha256", "sha256", 64)):
        value = version.get(field)
        valid = isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None
        identity[key] = value if valid else None
    return identity


def valid_install_record(record):
    """A last_install record exactly as this module writes it (a restored one is checked again)."""
    if not isinstance(record, dict) or not set(INSTALL_RECORD) <= set(record) <= set(INSTALL_RECORD + INSTALL_RECORD_EXTRA):
        return False
    reported = record["reported"]
    return (parse_tag(record["tag"]) is not None
            and (record["from_version"] is None or isinstance(record["from_version"], str)
                 and len(record["from_version"]) <= 64)
            and isinstance(record["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is not None
            and type(record["size"]) is int and 0 < record["size"] <= max_image_for_tag(record["tag"])
            and all(isinstance(record[key], str) and _UTC.fullmatch(record[key]) is not None
                    for key in ("started_at", "finished_at"))
            and type(record["duration_s"]) in (int, float) and 0 <= record["duration_s"] <= 3600
            and record["result"] in RESULTS and type(record["uploads"]) is int and record["uploads"] in (0, 1)
            and all(record.get(key) is None or type(record[key]) is int and 0 <= record[key] <= 4294967295
                    for key in INSTALL_RECORD_EXTRA)
            and (reported is None or isinstance(reported, dict) and reported == reported_identity(
                {"version": reported.get("version"), "source": reported.get("source_commit"),
                 "web_sha256": reported.get("web_sha256"), "sha256": reported.get("elf_sha256")})))


class HaGenerationStore:
    """The update list's stored generation and the time of its last good read, in Home Assistant's own storage
    (``.storage/emthera.update_list``): what the client of update_catalog.py keeps across restarts."""

    def __init__(self, hass):
        self._store = Store(hass, 1, STORE_KEY)

    async def async_load(self):
        return await self._store.async_load()

    async def async_save(self, data):
        await self._store.async_save(data)


def catalog_client(hass):
    """The one client of the update list for this installation (every entry of it shares the list)."""
    client = hass.data.get(CATALOG_KEY)
    if client is None:
        client = hass.data[CATALOG_KEY] = catalog.CatalogClient(HaGenerationStore(hass))
    return client


# What a person reads when the list cannot give an offer (release_summary), English and Dutch; {date} is the day of the
# last list that was verified. No Repair, no error: the installed version stays shown as the latest (decision D8).
CATALOG_TEXTS = {
    "stale": ("The update list is out of date, so no updates are offered for now.",
              "De updatelijst is verouderd, dus er worden voorlopig geen updates aangeboden."),
    "unreachable": ("The update list could not be refreshed since {date}.",
                    "De updatelijst kon sinds {date} niet worden vernieuwd."),
    "unreachable_unknown": ("The update list could not be reached.", "De updatelijst is niet bereikbaar."),
    "signature_invalid": ("The update list could not be verified, so no updates are offered.",
                          "De updatelijst kon niet worden gecontroleerd, dus er worden geen updates aangeboden."),
    "invalid": ("The update list cannot be used right now, so no updates are offered.",
                "De updatelijst is nu niet bruikbaar, dus er worden geen updates aangeboden."),
    "withdrawn": ("This firmware version was withdrawn by the maker.",
                  "Deze firmwareversie is door de maker ingetrokken."),
}


def catalog_sentence(status, checked, withdrawn, language):
    """The one short sentence for a state without an offer, or None when nothing is the matter."""
    index = 1 if str(language or "en").split("-")[0].lower() == "nl" else 0
    if status == catalog.STATUS_UNREACHABLE:
        key = "unreachable" if checked else "unreachable_unknown"
        return CATALOG_TEXTS[key][index].replace("{date}", (checked or "")[:10])
    if status in CATALOG_TEXTS:
        return CATALOG_TEXTS[status][index]
    return CATALOG_TEXTS["withdrawn"][index] if withdrawn else None


class E32FirmwareUpdate(UpdateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "e32_firmware"  # "Firmware" (EN/NL)
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES

    def __init__(self, hass, entry):
        self.hass, self._entry = hass, entry
        prefix = entry.data[CONF_TOPIC_PREFIX]
        self._attr_unique_id = f"{prefix}_e32_firmware"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, prefix)})
        self._offer = None  # the release of the verified update list that is offered (a dict of the list), or None
        self._check = None  # the last CatalogCheck (its status and reason go to the attributes)
        self._board = None  # the board the device reported in /status (None: it reports none = the old gateway)
        self._notes = {}  # (version, language) -> the verified notes text
        self._last_install = None
        self._lock = asyncio.Lock()
        self._failures = 0  # failed reads in a row (RETRY_DELAYS)
        self._retry = None  # the scheduled retry (async_call_later), or None
        self._confirmed_at = None  # time.monotonic() of the last version read from the E32 (own or the link's)

    @property
    def available(self):
        """Unavailable only while no installed version was ever known (never "unknown" for a
        known E32 that is briefly unreachable: its last known version stays)."""
        return self._attr_installed_version is not None

    def _set_installed(self, version):
        """A version the E32 reported (or that a restart restored); its channel follows.

        A version the release tags do not know (a local or development build) shows as installed, with no
        update offered (version_is_newer), instead of an entity that stays unavailable for good.
        """
        if parse_tag(version) is None and (type(version) is not str or not version.strip() or len(version) > 64):
            return False
        self._attr_installed_version = version
        if self._attr_latest_version is None:
            self._attr_latest_version = version
        self._sync_device_version()
        return True

    def _sync_device_version(self):
        """The E32 device shows its firmware version as its software version (beta.23)."""
        if getattr(self, "hass", None) is None or self.registry_entry is None or not self._attr_installed_version:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        device = registry.async_get(self.registry_entry.device_id) if self.registry_entry.device_id else None
        if device is not None and device.sw_version != self._attr_installed_version:
            registry.async_update_device(device.id, sw_version=self._attr_installed_version)
            # The room devices show the E32's version too (room_device, 1.3).
            from .room_device import sync_room_devices
            entry = getattr(self, "_entry", None)
            hub = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("heating_hub") if entry is not None else None
            if hub is not None:
                sync_room_devices(self.hass, entry, hub)

    def version_is_newer(self, latest_version, installed_version):
        latest, installed = parse_tag(latest_version), parse_tag(installed_version)
        # An unknown installed version (a development build) is never replaced by an offer.
        return latest is not None and installed is not None and latest > installed

    @property
    def last_install(self):
        return self._last_install

    @property
    def product(self):
        """The product of the update list this device belongs to: ``hub`` for the Hub's board, ``e32v2`` for the old
        gateway (also a device that reports no board), None for a board nobody knows (no offer is made for it)."""
        if not self._board:
            return "e32v2"
        return BOARD_PRODUCTS.get(self._board)

    @property
    def extra_state_attributes(self):
        attributes = {}
        check = self._check
        if check is not None:
            attributes.update(catalog_status=check.status, catalog_reason=check.reason,
                              catalog_generation=check.generation, last_checked=check.checked)
            if check.installed_withdrawn:
                attributes["installed_withdrawn"] = True
        if self._last_install:
            attributes["last_install"] = self._last_install
        return attributes or None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        record = last.attributes.get("last_install") if last is not None else None
        if self._last_install is None and isinstance(record, dict):
            record = {key: dict(value) if isinstance(value, dict) else value for key, value in record.items()}
            if valid_install_record(record):
                self._last_install = record
        # The last known versions survive a Home Assistant restart: the state before it,
        # else what the last install confirmed. The E32's MQTT topics carry no version.
        if self._attr_installed_version is None:
            restored = last.attributes.get("installed_version") if last is not None else None
            if not self._set_installed(restored) and self._last_install is not None:
                reported = self._last_install.get("reported")
                self._set_installed(reported.get("version") if isinstance(reported, dict) else None) or (
                    self._last_install["result"] == "installed" and self._set_installed(self._last_install["tag"]))
            latest = last.attributes.get("latest_version") if last is not None else None
            if parse_tag(latest) is not None and self._attr_installed_version is not None:
                self._attr_latest_version = latest
        self.async_on_remove(self._cancel_retry)
        hub = self._hub()
        if hub is not None and hasattr(hub, "add_firmware_listener"):
            self.async_on_remove(hub.add_firmware_listener(self._firmware_read))
        self._sync_device_version()

    def _hub(self):
        """The entry's heating hub (heating_link.heating_hub: made here when this platform asks first), or None."""
        entry = getattr(self, "_entry", None)
        entry_id = getattr(entry, "entry_id", None)
        data = getattr(self.hass, "data", None) if getattr(self, "hass", None) is not None else None
        if entry_id is None or not isinstance(data, dict) or not isinstance(data.get(DOMAIN, {}).get(entry_id), dict):
            return None
        from .heating_link import heating_hub
        return heating_hub(self.hass, entry)

    def _firmware_read(self, version):
        """HA-REREAD observer: the room-plan link read the E32's abilities again after a restart; the version it
        found is the installed one now (the E32 device and the room devices follow, _sync_device_version)."""
        if version is None or not self._set_installed(version):
            return
        self._confirmed_at = time.monotonic()
        self._failures = 0
        self._cancel_retry()
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()

    def _abilities_read_again(self, version):
        """HA-REREAD hook (plan 3.2), after a confirmed install: Home Assistant reads the E32's abilities again (the
        plan's features, its version and time zone) without a reload. Never in the way of the install's result."""
        try:
            link = getattr(self._hub(), "plan", None)
            if link is not None and hasattr(link, "request_refresh"):
                link.request_refresh(version)
        except Exception:  # noqa: BLE001 - the install itself succeeded
            _LOGGER.debug("Emthera: could not ask for the Hub's abilities after the install", exc_info=True)

    def _cancel_retry(self):
        if self._retry is not None:
            self._retry()
            self._retry = None

    def _schedule_retry(self):
        """The next read soon after a failure (1, 5, 15 min), then only the normal interval."""
        self._cancel_retry()
        if self._failures > len(RETRY_DELAYS) or self.hass is None:
            return
        delay = RETRY_DELAYS[self._failures - 1]

        async def retry(_now):
            self._retry = None
            await self.async_refresh()
        self._retry = async_call_later(self.hass, delay, retry)

    async def async_release_notes(self):
        """The notes of the offered release, from the verified notes file of the list (a file whose SHA-256 differs from
        the list's is never shown); the language of Home Assistant, English for every language but Dutch."""
        offer = self._offer
        if offer is None:
            return None
        language = "nl" if str(self.hass.config.language or "en").split("-")[0].lower() == "nl" else "en"
        key = (offer["version"], language)
        if key not in self._notes:
            text = await catalog_client(self.hass).async_fetch_notes(async_get_clientsession(self.hass), offer, language)
            if text is None:
                return None
            self._notes = {key: text}
        return self._notes[key]

    def _client(self):
        return ControllerClient(self._entry.data[CONTROLLER_ADDRESS])

    async def _sign_in(self, client, waits=()):
        """Sign in with the stored password, never with one the E32 refused before (one latch for every
        part of the entry, e32_access, R4-05); waits: the pauses for a free E32 web session."""
        from .e32_access import mark_rejected, password_rejected, report_password
        password = self._entry.data[CONTROLLER_PASSWORD]
        if password_rejected(self.hass, self._entry, password):
            raise ControllerLoginRejected()  # wait for the new password; Repairs asks for it
        try:
            if waits:
                await async_login_waiting(client, password, waits)
            else:
                await client.async_login(password)
        except ControllerLoginRejected:
            mark_rejected(self.hass, self._entry, password)
            raise
        report_password(self.hass, self._entry, getattr(client, "default_password", None))

    def _version_known(self):
        """The version was read from the E32 (here or by the room-plan link) less than a day ago, and the last read
        did not fail: the scheduled check need not sign in for it (HA-SESSIONS)."""
        return (self._confirmed_at is not None and not self._failures and self._attr_installed_version is not None
                and time.monotonic() - self._confirmed_at
                < (VERSION_READ_INTERVAL - VERSION_READ_SLACK).total_seconds())

    def _tell_hub(self, version):
        """HA-VERSION-START: what was just read is the hub's firmware version too (learned_overview.slow_correction
        reads it). The start-up read thus makes it known after a Home Assistant start, not only after an E32
        restart. No listener is told: this entity has the version already."""
        hub = self._hub()
        if hub is not None and hasattr(hub, "firmware_version") and type(version) is str and version:
            hub.firmware_version = version

    async def _read_board(self, client):
        """The board from /status (it decides which product's file this device may get). A device that reports no board
        is the old gateway (``_board`` None); a read that fails keeps what was known (it is never a failed version
        read: the offer simply keeps the last known product)."""
        try:
            status = await client.async_read("/status")
        except ControllerLoginRejected:
            raise
        except (ControllerLinkError, TimeoutError):
            return
        if isinstance(status, dict):
            board = status.get("board")
            self._board = board if isinstance(board, str) and 0 < len(board) <= 64 else None

    async def _read_version(self):
        """The installed version from the E32. Only a successful read changes it: an unreachable or busy E32
        (restarting, all web sessions in use) or a refused password keeps the last known one (and its channel).
        A refused password is a Repairs item."""
        try:
            async with self._client() as client:
                await self._sign_in(client)
                version = await client.async_read("/status/version")
                await self._read_board(client)
            if not self._set_installed(version.get("version") if isinstance(version, dict) else None):
                raise ControllerLinkError("controller_response_invalid")
            self._confirmed_at = time.monotonic()
            self._failures = 0
            self._cancel_retry()
            self._tell_hub(version.get("version"))
        except ControllerLoginRejected:
            pass  # Repairs asks for the new password; no retries until then
        except (ControllerLinkError, TimeoutError) as err:
            self._failures += 1
            _LOGGER.debug("Hub firmware version not read (%s); attempt %d", err, self._failures)
            self._schedule_retry()

    async def async_refresh(self, _now=None):
        """Read the installed version from the E32 and the offer from the signed update list of the website.

        ``_now``: the six-hourly schedule (async_track_time_interval). It skips the E32 while its version is known
        from the last day (_version_known); the start-up read and the retries (no ``_now``) always read it.
        A list that is old, unreachable or not verifiable gives no offer: the installed version stays the latest
        and ``release_summary`` says why in one sentence (never Unavailable, never a Repair).
        """
        if self._lock.locked():
            return
        if self.hass is None:
            # Home Assistant did not add this entity (disabled in the entity registry: it took ``hass`` away again).
            # The schedule of the set-up still calls here: nothing to keep current, no read and no request.
            return
        if _now is None or not self._version_known():
            await self._read_version()
        check = await catalog_client(self.hass).async_check(async_get_clientsession(self.hass), self.product,
                                                              self._attr_installed_version)
        self._check, self._offer = check, check.release
        self._attr_latest_version = self._offer["tag"] if self._offer else self._attr_installed_version
        self._attr_release_url = None
        language = self.hass.config.language
        if self._offer:
            summary = self._offer["summary"]["nl" if str(language or "en").split("-")[0].lower() == "nl" else "en"]
            self._attr_release_summary = summary
        else:
            self._attr_release_summary = catalog_sentence(check.status, check.checked, check.installed_withdrawn, language)
        if self.hass is not None and self.entity_id:
            self.async_write_ha_state()

    async def async_install(self, version, backup, **kwargs):
        async with self._lock:
            release, check = self._offer, self._check
            if release is None or (version is not None and version != release["tag"]):
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="firmware_release_unknown")
            self._attr_in_progress = True
            self.async_write_ha_state()
            started, clock, before = dt_util.utcnow(), time.monotonic(), self._attr_installed_version
            outcome = {"result": "download_failed", "uploads": 0, "reported": None,
                       "catalog_generation": check.generation, "key_slot": None}
            try:
                # The file: its size and SHA-256 from the list, then its own signed trailer for this device, then the
                # binding between the two (update_catalog.CatalogClient.async_fetch_file). Only that exact file is
                # pushed to the device, with the push and the confirmation loop of every release before.
                try:
                    image, info = await catalog_client(self.hass).async_fetch_file(
                        async_get_clientsession(self.hass), release, self.product, before)
                except catalog.CatalogError as err:
                    if err.reason != "unreachable":
                        outcome["result"] = "verification_failed"
                    raise _InstallFailed("the file was refused (%s)" % err.reason) from None
                outcome["result"], outcome["key_slot"] = "verification_failed", info["key_slot"]
                limit = MAX_IMAGE.get(self.product, MAX_IMAGE["e32v2"])
                if len(image) > limit:  # the list's own bound is the same slot; never upload more than it holds
                    raise _InstallFailed("firmware larger than the update slot")
                outcome["result"] = "upload_failed"
                async with self._client() as client:
                    # The owner pressed Install: wait for a free E32 web session (all 4 in use).
                    await self._sign_in(client, SESSION_WAITS)
                    await client.async_upload_firmware(image)
                outcome["uploads"], outcome["result"] = 1, "not_confirmed"
                # The E32 restarts itself; confirm the new version is running.
                for _ in range(36):
                    await asyncio.sleep(5)
                    try:
                        async with self._client() as client:
                            await self._sign_in(client)  # a refused password ends the wait (never tried twice)
                            running = await client.async_read("/status/version")
                        outcome["reported"] = reported_identity(running) or outcome["reported"]
                        if isinstance(running, dict) and running.get("version") == release["tag"]:
                            self._attr_installed_version = release["tag"]
                            self._confirmed_at = time.monotonic()
                            self._sync_device_version()
                            outcome["result"] = "installed"
                            self._abilities_read_again(release["tag"])
                            return
                    except ControllerLoginRejected:
                        raise  # never a second failed sign-in: Repairs asks for the new password
                    except ControllerLinkError:
                        continue
                raise _InstallFailed("the Hub did not report the new version within 3 minutes")
            except _InstallFailed as err:
                _LOGGER.warning("Emthera: the Hub firmware %s was not installed: %s", release["tag"], err)
                raise install_error(outcome["result"]) from None
            except ControllerLinkError as err:
                _LOGGER.warning("Emthera: the Hub firmware %s was not installed: Hub %s", release["tag"], err)
                raise install_error(outcome["result"], str(err) or type(err).__name__) from None
            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.warning("Emthera: the Hub firmware %s was not installed: %s", release["tag"],
                                type(err).__name__)
                raise install_error(outcome["result"]) from None
            finally:
                self._last_install = {
                    "tag": release["tag"], "from_version": before if isinstance(before, str) else None,
                    "sha256": release["sha256"], "size": release["size"], "started_at": utc_text(started),
                    "finished_at": utc_text(dt_util.utcnow()),
                    "duration_s": round(time.monotonic() - clock, 1), **outcome}
                self._attr_in_progress = False
                self.async_write_ha_state()


async def async_setup_firmware_update(hass, entry, async_add_entities, **add_options):
    """Only with a stored controller connection (address and admin password)."""
    if not entry.data.get(CONTROLLER_ADDRESS) or not entry.data.get(CONTROLLER_PASSWORD):
        return
    entity = E32FirmwareUpdate(hass, entry)
    async_add_entities([entity], **add_options)
    entry.async_on_unload(async_track_time_interval(hass, entity.async_refresh, CHECK_INTERVAL))
    hass.async_create_task(entity.async_refresh())
