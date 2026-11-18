"""The Hub's radio chip as its own firmware update (S-HA-2 package C; the update route's plan P5, C6-MAP section 5).

The Hub (the new board) has a second chip, an ESP32-C6, with firmware of its own and its own stream on the update website
(product ``hub-radio``). This module gives it a second update entity next to the Hub's own Firmware entity, which it never
touches (its own unique id ``<prefix>_radio_firmware`` and translation key ``radio_firmware``).

The entity exists only when the Hub reports a radio chip that takes firmware: ``GET /status/radio`` answers (the old gateway has
no such route), the chip is fitted and its own version is known. Without one nothing is created, so nothing is ever
Unavailable or Unknown for a device that has no radio chip. Once it exists it keeps its last known version when the Hub is
briefly unreachable, as the Hub's own entity does.

What it does:

- reads the chip's version and build id from ``/status/radio`` and the Hub's own version from ``/status/version``;
- asks the signed update list (update_catalog.py, the same client and the same checks as the Hub's own firmware) for
  ``hub-radio`` with the Hub's facts: this Hub's version (the release's lowest Hub version), the link protocol the chip speaks;
- offers a release only when it is newer than what the chip runs and the Hub is new enough; a newer file that needs a newer Hub
  says "the Hub must be updated first" and offers nothing;
- on Install: downloads the container and checks it completely before anything is sent (size and SHA-256 of the list, then the
  container's own structure, the Hub's policy, its signature and its parts, radio_container.py), uploads it to ``POST /radio/image``
  (the Hub checks it all again and stores it), then follows ``GET /status/radio`` until the chip reports the new build or the
  deadline passes. The Hub's own orchestrator puts the stored container on the chip.

The key table is the update list's, all zero until the owner provisions it: a normal installation is offered nothing and says so.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re

import aiohttp
from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .entity_guard import is_added
from . import firmware_update as main
from . import radio_container as container
from . import update_catalog as catalog
from .const import CONF_TOPIC_PREFIX, DOMAIN
from .failure_log import log_failure
from .controller_link import (ControllerLinkError, ControllerLoginRejected, RadioImageRejected, SESSION_WAITS,
                              async_login_waiting)
from .controller_setup_flow import CONTROLLER_ADDRESS, CONTROLLER_PASSWORD

_LOGGER = logging.getLogger(__name__)
PRODUCT = "hub-radio"
CHECK_INTERVAL = timedelta(hours=6)
INSTALL_WAIT_S = 600   # route R (the Hub's flasher) and route U (the chip itself) both end well inside ten minutes
POLL_S = 5
SETTLE_POLLS = 2       # a "failed" update state is believed only after this many reads (an older attempt's may still stand)
# The Hub's own version as its tag or plain text gives it: "v1.4.6-hub", "1.2.0", "v1.2.0+build" (the firmware's own rule).
HUB_VERSION = re.compile(r"v?(\d{1,5})\.(\d{1,5})\.(\d{1,5})(?:[-+].*)?")
BUILD_ID = re.compile(r"0x[0-9A-F]{8}")
# Install errors: where it stopped -> the translated error (exceptions.<key>).
INSTALL_ERRORS = {"download_failed": "radio_download_failed", "verification_failed": "radio_verification_failed",
                  "upload_failed": "radio_upload_failed", "not_confirmed": "radio_not_confirmed",
                  "hub_first": "radio_hub_update_first", "busy": "radio_busy"}
# What a person reads when there is no offer but something to say (release_summary), English and Dutch.
TEXTS = {
    "hub_first": ("The Hub must be updated first: the new radio firmware needs a newer Hub version.",
                  "De Hub moet eerst worden bijgewerkt: de nieuwe radiofirmware heeft een nieuwere versie van de Hub nodig."),
}


def hub_version_of(text):
    """(major, minor, patch) of the Hub's own version text, or None (an unreadable version fails the rule closed)."""
    match = HUB_VERSION.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def radio_facts(status):
    """What a ``GET /status/radio`` says that this entity uses: {"fitted", "version", "build_id", "major", "update", "error"},
    each None when the Hub does not say it (a value is never made up). The chip's version text is the Hub's own cut: printable
    ASCII only."""
    if not isinstance(status, dict):
        return None
    version = status.get("version")
    version = version if isinstance(version, str) and 0 < len(version) <= 32 and version.isprintable() else None
    build = status.get("build_id")
    protocol = status.get("protocol")
    major = protocol.get("major") if isinstance(protocol, dict) else None
    update = status.get("update") if isinstance(status.get("update"), dict) else {}
    error = update.get("error")
    return {"fitted": status.get("fitted") is True,
            "version": version,
            "build_id": build if isinstance(build, str) and BUILD_ID.fullmatch(build) else None,
            "major": major if type(major) is int and 1 <= major <= 65535 else None,
            "update": update.get("state") if isinstance(update.get("state"), str) else None,
            "error": error if isinstance(error, str) and re.fullmatch(r"[a-z0-9_]{1,48}", error) else None}


def takes_firmware(facts):
    """The Hub reports a radio chip that takes firmware: fitted, and talking (its own version is known)."""
    return facts is not None and facts["fitted"] and facts["version"] is not None


class RadioFirmwareUpdate(UpdateEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "radio_firmware"  # "Radio firmware" (EN) / "Radiofirmware" (NL)
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, hass, entry, facts):
        self.hass, self._entry = hass, entry
        prefix = entry.data[CONF_TOPIC_PREFIX]
        self._attr_unique_id = f"{prefix}_radio_firmware"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, prefix)})
        self._facts = facts
        self._hub_version = None
        self._check = None
        self._offer = None
        self._lock = asyncio.Lock()
        self._attr_installed_version = facts["version"]
        self._attr_latest_version = facts["version"]

    # -- what the entity says --------------------------------------------------------------------------------------
    @property
    def extra_state_attributes(self):
        attributes = {}
        if self._facts:
            attributes.update(radio_build_id=self._facts["build_id"], radio_update_state=self._facts["update"],
                              radio_update_error=self._facts["error"])
        check = self._check
        if check is not None:
            attributes.update(catalog_status=check.status, catalog_reason=check.reason,
                              catalog_generation=check.generation, last_checked=check.checked)
            if check.hub_first is not None and self._hub_version is not None:
                attributes["hub_update_needed"] = True
        return attributes

    def _device(self):
        """The facts the selection needs of this device: the Hub's version and the link protocol the chip speaks."""
        major = (self._facts or {}).get("major")
        link = (major, major) if major else container.LINK_PROTOCOL
        hub = self._hub_version
        return {"product": PRODUCT, "board": catalog.BOARDS[PRODUCT], "target": container.TARGET,
                "link_protocol": {"min": link[0], "max": link[1]},
                "hub_version": "%d.%d.%d" % hub if hub else "0.0.0"}, link, hub

    async def _sign_in(self, client, waits=()):
        """The stored password, never one the Hub refused before (the integration's one latch, e32_access)."""
        from .e32_access import mark_rejected, password_rejected, report_password
        password = self._entry.data[CONTROLLER_PASSWORD]
        if password_rejected(self.hass, self._entry, password):
            raise ControllerLoginRejected()
        try:
            if waits:
                await async_login_waiting(client, password, waits)
            else:
                await client.async_login(password)
        except ControllerLoginRejected:
            mark_rejected(self.hass, self._entry, password)
            raise
        report_password(self.hass, self._entry, getattr(client, "default_password", None))

    def _client(self):
        return main.ControllerClient(self._entry.data[CONTROLLER_ADDRESS])

    async def _read(self):
        """The radio chip's status and the Hub's version; a read that fails keeps what was known."""
        try:
            async with self._client() as client:
                await self._sign_in(client)
                facts = radio_facts(await client.async_radio_status())
                version = await client.async_read("/status/version")
        except ControllerLoginRejected:
            return
        except (ControllerLinkError, TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("Emthera: the radio chip's status was not read (%s)", err)
            return
        if facts is not None:
            self._facts = facts
            if facts["version"] is not None:
                self._attr_installed_version = facts["version"]
        self._hub_version = hub_version_of(version.get("version")) if isinstance(version, dict) else None

    async def async_refresh(self, _now=None):
        """Read the chip and the Hub, then the offer from the signed update list. A list that is old, unreachable or not
        verifiable gives no offer and one sentence (never Unavailable, never a Repair); neither does a radio that is
        current, or a newer file the Hub is too old for (then: the Hub must be updated first)."""
        if self._lock.locked():
            return
        if self.hass is None:
            return  # not added by Home Assistant (disabled in the entity registry): no read and no request
        await self._read()
        device, _link, _hub = self._device()
        check = await main.catalog_client(self.hass).async_check(main.async_get_clientsession(self.hass), PRODUCT,
                                                                 self._attr_installed_version, device)
        offer = check.release
        if offer is not None and self._facts and self._facts["build_id"] == container.link_build_id(offer["build_id"]):
            offer = None   # the chip already runs exactly that build
        if self._hub_version is None:
            offer = None   # an unknown Hub version fails closed, as the Hub itself does
        self._check, self._offer = check, offer
        self._attr_latest_version = offer["version"] if offer else self._attr_installed_version
        self._attr_release_url = None
        language = self.hass.config.language
        index = 1 if str(language or "en").split("-")[0].lower() == "nl" else 0
        if offer:
            self._attr_release_summary = offer["summary"]["nl" if index else "en"]
        elif check.hub_first is not None and self._hub_version is not None:
            self._attr_release_summary = TEXTS["hub_first"][index]
        else:
            self._attr_release_summary = main.catalog_sentence(check.status, check.checked, check.installed_withdrawn, language)
        if is_added(self):
            self.async_write_ha_state()

    # -- install ---------------------------------------------------------------------------------------------------
    @staticmethod
    def _error(key, **placeholders):
        if placeholders.get("error") or placeholders.get("reason"):
            log_failure(INSTALL_ERRORS[key], placeholders.get("error") or placeholders.get("reason"))
        return HomeAssistantError(translation_domain=DOMAIN, translation_key=INSTALL_ERRORS[key],
                                  translation_placeholders=placeholders or None)

    async def async_install(self, version, backup, **kwargs):
        async with self._lock:
            offer, check = self._offer, self._check
            if offer is None or (version is not None and version != offer["version"]):
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="radio_release_unknown")
            self._attr_in_progress = True
            self.async_write_ha_state()
            device, link, hub = self._device()
            try:
                # The file, checked completely in Python first: nothing a Hub would refuse is ever sent to it.
                try:
                    data, info = await main.catalog_client(self.hass).async_fetch_container(
                        main.async_get_clientsession(self.hass), offer, hub_version=hub, link_protocol=link)
                except catalog.CatalogError as err:
                    _LOGGER.warning("Emthera: the radio firmware %s was not installed: the file was refused (%s)",
                                    offer["version"], err.reason)
                    if err.reason == "hub_too_old":
                        raise self._error("hub_first") from None
                    raise self._error("download_failed" if err.reason == "unreachable" else "verification_failed",
                                      reason=err.reason) from None
                want = container.link_build_id(info["build_id"])
                try:
                    async with self._client() as client:
                        await self._sign_in(client, SESSION_WAITS)
                        await client.async_upload_radio_container(data)
                except RadioImageRejected as err:
                    _LOGGER.warning("Emthera: the Hub refused the radio firmware %s (%s)", offer["version"], err.error)
                    raise self._error("hub_first" if err.error == "hub_too_old"
                                      else "busy" if err.error == "busy" else "upload_failed", error=err.error) from None
                except (ControllerLinkError, TimeoutError, aiohttp.ClientError) as err:
                    raise self._error("upload_failed", error=str(err) or type(err).__name__) from None
                # The Hub's orchestrator puts the stored container on the chip; follow the status until it reports the build.
                for poll in range(INSTALL_WAIT_S // POLL_S):
                    await asyncio.sleep(POLL_S)
                    try:
                        async with self._client() as client:
                            await self._sign_in(client)
                            facts = radio_facts(await client.async_radio_status())
                    except ControllerLoginRejected:
                        raise
                    except (ControllerLinkError, TimeoutError, aiohttp.ClientError):
                        continue
                    if facts is None:
                        continue
                    self._facts = facts
                    if facts["build_id"] == want and facts["version"] is not None:
                        self._attr_installed_version = facts["version"]
                        self._attr_latest_version = facts["version"]
                        self._offer = None
                        return
                    if facts["update"] == "failed" and poll + 1 >= SETTLE_POLLS:
                        raise self._error("upload_failed", error=facts["error"] or "failed")
                raise self._error("not_confirmed")
            except ControllerLoginRejected:
                raise self._error("upload_failed", error="controller_auth_failed") from None
            finally:
                self._attr_in_progress = False
                self.async_write_ha_state()


async def async_setup_radio_update(hass, entry, async_add_entities, **add_options):
    """Create the radio update entity when (and only when) the Hub reports a radio chip that takes firmware. Looked at once
    now and then every six hours until the entity exists; a device without the route (the old gateway), without a chip or
    with a silent one gets nothing, and the main Firmware entity is not involved."""
    if not entry.data.get(CONTROLLER_ADDRESS) or not entry.data.get(CONTROLLER_PASSWORD):
        return
    state = {"entity": None, "busy": False}

    async def look(_now=None):
        if state["entity"] is not None or state["busy"]:
            return
        state["busy"] = True
        try:
            probe = RadioFirmwareUpdate(hass, entry, {"version": None, "build_id": None, "fitted": False, "major": None,
                                                      "update": None, "error": None})
            async with probe._client() as client:
                await probe._sign_in(client)
                facts = radio_facts(await client.async_radio_status())
        except Exception as err:  # noqa: BLE001 - no route, no chip, no answer: no entity, never an error in the log
            _LOGGER.debug("Emthera: no radio chip that takes firmware (%s)", type(err).__name__)
            return
        finally:
            state["busy"] = False
        if not takes_firmware(facts):
            return
        entity = state["entity"] = RadioFirmwareUpdate(hass, entry, facts)
        async_add_entities([entity], **add_options)
        entry.async_on_unload(async_track_time_interval(hass, entity.async_refresh, CHECK_INTERVAL))
        hass.async_create_task(entity.async_refresh())

    hass.async_create_task(look())
    entry.async_on_unload(async_track_time_interval(hass, look, CHECK_INTERVAL))
