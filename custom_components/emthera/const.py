"""Constants for the OpenThermostat room integration."""

from homeassistant.const import Platform

DOMAIN = "emthera"
# hass.data[DOMAIN] holds only {entry id: that entry's state}; what every entry shares lives in
# hass.data[SHARED] (R4-31: the Repairs bookkeeping, the information notes).
SHARED = DOMAIN + "_shared"


def identifier_pairs(identifiers):
    """(domain, value) of every device identifier that is a pair of two texts. Home Assistant allows an identifier of any
    length (the HomeKit bridge's device uses three parts) and of any type (a Tesla device uses an integer), so nothing may
    unpack one as a pair or assume a part is text: every other identifier is skipped."""
    return [(i[0], i[1]) for i in identifiers or ()
            if isinstance(i, (tuple, list)) and len(i) == 2 and isinstance(i[0], str) and isinstance(i[1], str)]
# Device-registry manufacturer of every OpenThermostat device (metadata only: identifiers stay).
MANUFACTURER = "Emthera"
# Default name of the E32 product device: the product's name, the same in every language. It sets the
# device's own name only; a name the user gave it in Home Assistant (name_by_user) always stays (R4-22).
E32_DEVICE_NAME = "Emthera Hub"
# What older releases stored; renamed once at setup (__init__._rename_old_manufacturer).
OLD_MANUFACTURER = "intuibase"
CONF_TOPIC_PREFIX = "topic_prefix"
# MQTT prefix of a new installation (the Hub's firmware default is the same). Existing entries keep their stored
# prefix (the gateway's firmware default is "openthermostat", older firmware and installations use "ib-therm");
# discovery accepts any prefix.
DEFAULT_TOPIC_PREFIX = "emthera"
# What a new installation of the release before the rename defaulted to (and what the gateway's firmware still ships).
GATEWAY_TOPIC_PREFIX = "openthermostat"
CONF_CREATE_DASHBOARD = "create_dashboard"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.NUMBER, Platform.SENSOR]

# Daily summary and warnings (1.0, daily_summary.py and heating_problem.py). One place for the thresholds.
# A day counts as complete with at least this much observed E32 data; a shorter day is "partial".
SUMMARY_COMPLETE_DAY_HOURS = 20
SUMMARY_DAYS_KEPT = 21
# A burner run shorter than this is a short run (counted per day; the E32's own short-cycling flag is separate).
SUMMARY_SHORT_RUN_MINUTES = 10
# A rise of the room's target by at least this starts a "time to target" measurement ...
SUMMARY_TARGET_STEP_C = 0.5
# ... which ends when the room is within this of the target ...
SUMMARY_TARGET_REACHED_C = 0.2
# ... and counts as on time within this many minutes.
SUMMARY_TARGET_ON_TIME_MINUTES = 120
# After that time, every minute the room is more than this below its target counts as a missed comfort minute.
SUMMARY_MISSED_MARGIN_C = 0.5
# Warning: a room that asks for heat stays more than this below its target for this long.
WARN_ROOM_SLOW_MARGIN_C = 0.5
WARN_ROOM_SLOW_HOURS = 3
# Warning: the E32 is online but Home Assistant has no working session with it for this long.
WARN_SESSION_LOST_MINUTES = 15
