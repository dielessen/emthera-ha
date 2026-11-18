"""The settings panel's tester screen (Settings -> Installation -> Tester program, ``#installation/tester``).

The run itself is tester_run.TesterRun; this module is its door to the panel: the screen's model (the switch, and under
``live.run`` the run as the panel draws it) and the actions the panel calls (``settings/action``, administrators only).
Every action answers ``{"run": <the run's model>}``, so the panel redraws from the answer; a refusal is a SettingsError
the panel explains (the keys are in frontend/emthera-settings-installation_tester.js).

Actions: tester_state (the panel's poll: no request to the Hub unless the screen needs one), tester_start {recording,
consent}, tester_step {step} (the wizard step), tester_mark {kind}, tester_display {state, code, temp, country}, tester_photo {upload_id}, tester_photo_remove,
tester_finish, tester_save, tester_restart (back to the start: the files and the run go), tester_new_code.
"""
from __future__ import annotations

from .settings import LIVE, SettingsError, language


def _lang(hass, values):
    wanted = values.get("language") if isinstance(values, dict) else None
    return language(hass, wanted if type(wanted) is str else None)


def _monitor(hass, entry):
    from .boiler_share import STATE_KEY, tester_on
    from .const import DOMAIN
    monitor = (hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}).get(STATE_KEY)
    if monitor is None or not tester_on(entry):
        raise SettingsError("tester_off")
    return monitor


async def _run(hass, entry):
    run = _monitor(hass, entry).run
    await run.async_load()  # idempotent: the first call after the switch loads the record
    return run


def _failed(err):
    from .tester_run import RunError
    if isinstance(err, RunError):
        return SettingsError(err.key, err.field or "base", **err.placeholders)
    return err


async def read_tester(hass, entry, done=None, values=None):
    """The screen's model: the switch, whether the Hub is connected, and the run (None while the program is off)."""
    from .boiler_share import tester_on
    from .e32_system import link_for
    on = tester_on(entry)
    link = link_for(hass, entry)
    run_model = None
    if on and link is not None:
        try:
            run = await _run(hass, entry)
            await run.async_refresh()
            run_model = run.model(_lang(hass, values))
        except SettingsError:
            run_model = None
    return {"screen": "tester", "tester_enabled": on, "e32": link is not None, LIVE: {"run": run_model, "done": done}}


async def save_screen(hass, entry, values):
    """The switch (the only field of the screen): on only with the Hub connected; off removes the run and its files."""
    from .boiler_share import save_tester, tester_on
    from .e32_system import link_for
    wanted = values.get("tester_enabled")
    if type(wanted) is not bool:
        raise SettingsError("setup_invalid", "tester_enabled")
    if wanted != tester_on(entry):
        if link_for(hass, entry) is None:
            raise SettingsError("connect_e32")
        save_tester(hass, entry, wanted)
        return await read_tester(hass, entry, "switched_on" if wanted else "tester_switched_off", values)
    return await read_tester(hass, entry, None, values)


def _answer(run, hass, values):
    return {"run": run.model(_lang(hass, values))}


async def _call(hass, entry, values, action):
    from .controller_link import ControllerLinkError
    from .e32_system import failure
    run = await _run(hass, entry)
    try:
        await action(run)
    except ControllerLinkError as err:
        key, placeholders = failure(err)
        raise SettingsError(key, **placeholders) from None
    except Exception as err:  # noqa: BLE001 - only the run's own refusals are translated; anything else is a bug
        translated = _failed(err)
        if translated is err:
            raise
        raise translated from None
    return _answer(run, hass, values)


async def tester_state(hass, entry, item, values):
    run = await _run(hass, entry)
    await run.async_refresh()
    return _answer(run, hass, values)


async def tester_start(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_start(values.get("recording"), values.get("consent")))


async def tester_step(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_step(values.get("step")))


async def tester_mark(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_mark(values.get("kind")))


async def tester_display(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_display(
        values.get("state"), values.get("code"), values.get("temp"), values.get("country")))


async def tester_photo(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_photo(values.get("upload_id")))


async def tester_photo_remove(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_remove_photo())


async def tester_finish(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_finish())


async def tester_save(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_save(_lang(hass, values)))


async def tester_restart(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_restart_run())


async def tester_test_page(hass, entry, item, values):
    """The Hub's own page of the boiler test (the run reads the test the Hub keeps and never builds one). Given only when
    the administrator taps the button: the address is not in the screen's model."""
    run = await _run(hass, entry)
    link = run._link()
    if link is None:
        raise SettingsError("connect_e32")
    page = "boiler_ot.html" if run._is_ot() else "boiler_test.html"   # an OpenTherm Hub has its own page of the boiler test
    return {"url": f"{link.address.rstrip('/')}/{page}"}


async def tester_new_code(hass, entry, item, values):
    return await _call(hass, entry, values, lambda run: run.async_new_code())


ACTIONS = {"tester_state": tester_state, "tester_step": tester_step, "tester_start": tester_start, "tester_mark": tester_mark, "tester_display": tester_display,
           "tester_photo": tester_photo, "tester_photo_remove": tester_photo_remove, "tester_finish": tester_finish,
           "tester_save": tester_save, "tester_restart": tester_restart, "tester_new_code": tester_new_code,
           "tester_test_page": tester_test_page}
