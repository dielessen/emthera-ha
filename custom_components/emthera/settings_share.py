"""The settings panel's block "Share data with Emthera" (TESTER-AUTO-5, Settings -> Installation, under the list of the Hub's own screens).

The Hub shares the boiler's data by itself after ONE permission (design TESTER-AUTO, section 7b). Home Assistant sends nothing: this module only
reads the Hub's ``GET /share`` and writes the user's permission and pick through ``POST /share/permission`` and ``POST /share/pick``. The panel
asks for the block with ``share_state``; an answer of ``{"share": None}`` (the old gateway, a Hub without the routes, a boiler link without a
collector, a Hub that cannot be reached) means the block is not shown. No entity, no Repairs item, no notification.

The permission text is NOT written here: it comes from ``share_format/consent_auto.json`` (the one source; the Hub serves a byte for byte copy), in
the viewer's language, with the form of the recording paragraph that belongs to the boiler link. The pick's list is the boiler catalogue Home
Assistant ships (the same list the Hub's "Boiler model" pick uses), grouped by brand.

Actions (administrators only, like every action of the panel; ``values`` may carry ``language``):

- ``share_state`` -> ``{"share": None | {"doc", "text", "version", "boilers"}}``
- ``share_permission {on: bool}`` -> the same; ``on: true`` sends the text's version, the Hub refuses another one
- ``share_pick {brand, model} | {other} | {}`` -> the same (``{}`` clears the pick)
- ``share_forget`` -> the same: switches sharing off and asks Emthera to delete what this Hub shared (``POST /share/forget`` with ``{}``; AUTO-4B).
  The document's ``forget`` member says how far the request is: null, or ``{state, asked_at, sent_at, last_try}``.
"""
from __future__ import annotations

import re

from .settings import SettingsError, language

# The members of the Hub's document the panel may see (the contract's names, unchanged; `row` names a control-table row and stays on the Hub).
DOC_KEYS = ("supported", "configured", "permission", "boiler", "state", "seen", "waiting_for", "days_left", "sent_at", "last_try", "reference", "forget")
OTHER_MAX = 40
PHRASE = re.compile(r"^[A-Za-z0-9 \-/.]{1,40}$")  # what the Hub accepts for a brand, a model or a free text


def _boilers():
    """[{brand, types}] of the boiler catalogue Home Assistant ships (the selectable models), as the Hub's pick lists them."""
    from .e32_boiler_model import models
    brands: dict[str, set[str]] = {}
    for item in models().values():
        if type(item) is not dict or item.get("selectable", True) is False:
            continue
        brand, name = item.get("brand"), item.get("name")
        if type(brand) is not str or type(name) is not str or not brand or not name:
            continue
        brands.setdefault(brand, set()).add(name[len(brand) + 1:] if name.startswith(brand + " ") else name)
    return [{"brand": b, "types": sorted(brands[b], key=str.casefold)} for b in sorted(brands, key=str.casefold)]


def _text(lang, link="ems"):
    from .share_format import consent
    return consent.text_auto(consent.load_auto(), lang, link)


def _version():
    from .share_format import consent
    return consent.version(consent.load_auto())


def _clean(doc):
    """The contract's document cut to the members the panel reads; None for anything that is not a document of a Hub that shares."""
    if type(doc) is not dict or doc.get("supported") is not True:
        return None
    if type(doc.get("permission")) is not dict or type(doc.get("boiler")) is not dict:
        return None
    return {key: doc[key] for key in DOC_KEYS if key in doc}


async def _view(hass, entry, doc, values):
    clean = _clean(doc)
    if clean is None:
        return None
    lang = language(hass, values.get("language") if isinstance(values, dict) else None)
    text = await hass.async_add_executor_job(_text, lang)
    # the boiler catalogue is a packaged file (ems_devices.products): read once, never in the event loop
    return {"doc": clean, "text": text, "version": await hass.async_add_executor_job(_version),
            "boilers": await hass.async_add_executor_job(_boilers)}


async def _call(hass, entry, call, write):
    """call(client) in one sign-in: the Hub's document, or None when this Hub has nothing to say about sharing."""
    from .controller_link import ControllerLinkError, HeatingPlanRejected
    from .e32_system import async_e32_call, link_for
    link = link_for(hass, entry)
    if link is None:
        return None
    try:
        return await async_e32_call(link, call, write=write)
    except HeatingPlanRejected as err:
        # 409: a link without a collector (not_supported), else the Hub is busy (a boiler test runs; the answer is a text or device_busy)
        key = ("share_no_storage" if (err.status, err.error) == (503, "no_storage") else "share_refused" if err.status != 409 else "share_not_supported" if err.error == "not_supported"
               else "share_permission_off" if err.error == "permission_off" else "share_nothing_sent" if err.error == "nothing_sent"
               else "share_forget_pending" if err.error == "forget_pending" else "share_busy")
        raise SettingsError(key, error=err.error) from None
    except ControllerLinkError:
        if write:
            raise SettingsError("share_refused", error="unreachable") from None
        return None  # not reachable now, no such route, or not signed in: the block is simply not shown


async def share_state(hass, entry, item, values):
    return {"share": await _view(hass, entry, await _call(hass, entry, lambda c: c.async_share(), False), values)}


async def share_permission(hass, entry, item, values):
    on = values.get("on") if isinstance(values, dict) else None
    if type(on) is not bool:
        raise SettingsError("setup_invalid", "on")
    from .controller_link import SHARE_PERMISSION
    document = {"on": True, "text_version": await hass.async_add_executor_job(_version)} if on else {"on": False}
    doc = await _call(hass, entry, lambda c: c.async_share(SHARE_PERMISSION, document), True)
    return {"share": await _view(hass, entry, doc, values)}


async def share_pick(hass, entry, item, values):
    """A pick from the list (brand and model), the boiler that is not in the list (other), or nothing (clears it)."""
    if not isinstance(values, dict):
        raise SettingsError("setup_invalid", "pick")
    brand, model, other = values.get("brand"), values.get("model"), values.get("other")
    if other is not None:
        if type(other) is not str or not PHRASE.fullmatch(other) or brand is not None or model is not None:
            raise SettingsError("setup_invalid", "other")
        document = {"other": other}
    elif brand is not None or model is not None:
        if type(brand) is not str or type(model) is not str or not PHRASE.fullmatch(brand) or not PHRASE.fullmatch(model):
            raise SettingsError("setup_invalid", "model")
        document = {"brand": brand, "model": model}
    else:
        document = {}
    from .controller_link import SHARE_PICK
    doc = await _call(hass, entry, lambda c: c.async_share(SHARE_PICK, document), True)
    return {"share": await _view(hass, entry, doc, values)}

async def share_forget(hass, entry, item, values):
    """Sharing off and ONE request to Emthera to delete what this Hub shared; the Hub sends it by itself (tries again later, gives up after 14 days)."""
    from .controller_link import SHARE_FORGET
    doc = await _call(hass, entry, lambda c: c.async_share(SHARE_FORGET, {}), True)
    return {"share": await _view(hass, entry, doc, values)}


ACTIONS = {"share_state": share_state, "share_permission": share_permission, "share_pick": share_pick, "share_forget": share_forget}
