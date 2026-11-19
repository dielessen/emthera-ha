# HA 1.4.8 — the move to Emthera, made sturdy
<!-- user-release-notes:v2:en -->

This version repairs the move from OpenThermostat to Emthera. **Installed 1.4.7 and the move did not complete?
Nothing of yours was changed. Update Emthera to 1.4.8 in the Marketplace and restart Home Assistant; the move then
runs.** It works with firmware 1.4.6 on the BBQKees Gateway E32 V2; the firmware is not part of this release. Needs
Home Assistant 2026.10.0 or newer.

## New

- Nothing new: this version only repairs the move.

## Fixed

- The move stopped with "The move did not complete" on a Home Assistant that has a device of another integration
  with a three-part identifier, for example the HomeKit bridge. Nothing was changed or lost when that happened.
- Apple Home keeps your thermostats: the move now carries the HomeKit bridge's accessory numbers to the new name.
  Before, Apple Home would have shown them as new accessories after the move. If a bridge cannot be carried, the
  move goes on and its message says so.
- The move is sturdier at its edges: it waits until the previous version has written its files, copies again when a
  file changed meanwhile, leaves damaged files of Home Assistant alone, puts everything back when it fails, and
  finishes or undoes by itself at the next start after a power cut.
- When the previous version does not stop cleanly, the move does not start and says in one sentence what to do.
- Rooms, valves, room groups and the diagnostics no longer trip over a device with such an identifier either.

## Updating

- Installed 1.4.7 and the move did not complete: update Emthera in the Marketplace and restart Home Assistant. The
  move then runs by itself within a few minutes, or press Submit again under Settings → Devices & services → Add
  integration → Emthera. It takes about half a minute.
- Not moved yet: the steps are in the manual, section 9.4:
  https://github.com/dielessen/emthera-ha/blob/main/docs/INSTALL.md#94-update-from-the-release-before-the-rename-146-and-older
- Needs Home Assistant 2026.10.0 or newer, with the MQTT integration. Tested on Home Assistant 2026.10.0, 2026.10.4
  and 2026.11.1.

## Limitations

- Works with a BBQKees Gateway E32 V2 on firmware 1.4.6, or an Emthera Hub.
- The Hub support does nothing until a Hub is connected.
- Carrying the HomeKit accessory numbers was tested against a copy of Home Assistant's own rules, not yet against a
  real HomeKit bridge.
- On Home Assistant 2026.10 with HACS only the way by hand of section 9.4 has been tried.
- The firmware update entity offers nothing today.

# HA 1.4.7 — the integration is now called Emthera, in its own repository
<!-- user-release-notes:v2:en -->

The integration has a new name, **Emthera**, and a new repository:
https://github.com/dielessen/emthera-ha. It works with firmware 1.4.6 on the
BBQKees Gateway E32 V2; the firmware itself is not part of this release and
stays 1.4.6. Needs Home Assistant 2026.10.0 or newer.

**Coming from OpenThermostat 1.4.6 or older? Do not use "Update" on the old
OpenThermostat entry and do not delete the integration under Settings →
Devices & services.** Your installation, entities, history and automations
move by themselves, and the move can be undone. The steps are under
Updating.

## New

- The pages and texts say "Hub" where they said "E32" (the device is the
  same). Entity IDs stay.
- The firmware update entity reads the signed update list of emthera.nl. Today
  that list is not published, so the entity says in one sentence that the
  update list could not be verified and offers nothing.
- The integration also contains support for the Emthera Hub, which is in
  development and not for sale yet (see https://emthera.nl). It does nothing
  until a Hub is connected.

## Fixed

- Home Assistant 2026.11 no longer logs "deprecated" warnings about the
  thermostats (they stop working in Home Assistant 2027.11).
- An entity you disabled no longer breaks the update of other entities
  ("setting up the metrics failed"), and a disabled update entity no longer
  reads the device or asks for the update list.
- Home Assistant no longer warns about a "blocking call" when the integration
  starts: its own files are read outside Home Assistant's event loop.
- The notice about a new version of the integration also appears when the
  update comes from the new repository.

## Updating

You do not update, you move. The steps are in the manual, section 9.4:
https://github.com/dielessen/emthera-ha/blob/main/docs/INSTALL.md#94-update-from-the-release-before-the-rename-146-and-older

- Add the new repository to the Marketplace by link, install Emthera and
  restart Home Assistant; the old actions (`open_thermostat.…`) keep working
  throughout the 1.x releases.
- Needs Home Assistant 2026.10.0 or newer, with the MQTT integration. Tested
  on Home Assistant 2026.10.0, 2026.10.4 and 2026.11.1.

## Limitations

- Works with a BBQKees Gateway E32 V2 on firmware 1.4.6, or an Emthera Hub.
- The Hub support does nothing until a Hub is connected.
- On Home Assistant 2026.10 with HACS only the way by hand of section 9.4 has
  been tried.
- The firmware update entity offers nothing today (see New).

Earlier versions were released as OpenThermostat: see the [releases of the old repository](https://github.com/dielessen/openthermostat-ha/releases).
