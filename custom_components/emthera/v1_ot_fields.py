"""The values of an OpenTherm boiler that have no counterpart among the existing boiler values (boiler.fields.v3).

The values that mean the same as an existing boiler value (flow, return, modulation, pressure, hot water, outdoor,
the status bits, the counters) never come here: ot_fields.py hands them to the existing boiler field records, so the
same entities, history and dashboard tiles show them. What is left (status and fault flags, the boiler's identity and
limits, pump counters) gets an entity per value, made only after the boiler reported a first real value for it
(nothing Unknown or Unavailable for a value the boiler never has), plus one "Boiler link" sensor with the stage of the
link. The table is data (ot_table.py): no code per id.

Unique IDs: ``{prefix}_ot_field_<id>`` (whole value), ``{prefix}_ot_field_<id>_hi|lo`` (one byte) and
``{prefix}_ot_field_<id>_hi|lo_<bit>`` (one flag bit); ``{prefix}_boiler_link`` for the link.
"""
import logging

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_TOPIC_PREFIX, DOMAIN
from .ot_fields import OWN_POINTS, STAGES

_LOGGER = logging.getLogger(__name__)

STALE_CHECK = timedelta(seconds=15)
# Classes of the id table whose values are for diagnosis, not for every day.
DIAGNOSTIC_CLASSES = frozenset({"configuration", "version", "parameter", "counter", "fault"})
UNITS = {"degC": UnitOfTemperature.CELSIUS, "%": PERCENTAGE, "kW": UnitOfPower.KILO_WATT, "h": UnitOfTime.HOURS}
DEVICE_CLASSES = {"degC": SensorDeviceClass.TEMPERATURE, "kW": SensorDeviceClass.POWER, "h": SensorDeviceClass.DURATION}


def unique_id(prefix, point):
    return f"{prefix}_ot_field_{point.id}" + ("" if point.part == "w" else f"_{point.part}") + (
        "" if point.bit is None else f"_{point.bit}")


def link_unique_id(prefix):
    return f"{prefix}_boiler_link"


class _OtEntity:
    """What the value entities of one OpenTherm boiler share: the cache of the client, the availability."""
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, prefix, client, product=True):
        from homeassistant.helpers.device_registry import DeviceInfo
        from .ems_devices import boiler_device_info
        self.client = client
        # A product entry shows them on the boiler device with the other boiler values; an older entry on its device.
        self._attr_device_info = boiler_device_info(prefix) if product else DeviceInfo(identifiers={(DOMAIN, prefix)})
        self.added = False
        self.written = None

    @property
    def cache(self):
        return self.client.boiler_fields

    @property
    def available(self):
        # Like every retained boiler value: unavailable only while the device itself is offline or silent; a value
        # the boiler has none of now reads unknown.
        return self.cache.alive(self.client.clock())

    def signature(self):
        return (self.available, self.value() if self.available else None)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.added, self.written = True, None

    async def async_will_remove_from_hass(self):
        self.added = False
        await super().async_will_remove_from_hass()


class OtValueSensor(_OtEntity, SensorEntity):
    def __init__(self, prefix, client, point, product=True):
        super().__init__(prefix, client, product)
        self.point = point
        self._attr_unique_id = unique_id(prefix, point)
        self._attr_translation_key = "ot_" + point.key
        if point.unit in UNITS:
            self._attr_native_unit_of_measurement = UNITS[point.unit]
        if point.unit in DEVICE_CLASSES:
            self._attr_device_class = DEVICE_CLASSES[point.unit]
        if point.cls in DIAGNOSTIC_CLASSES:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if point.cls == "counter":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        if point.kind != "f88":
            self._attr_suggested_display_precision = 0

    def value(self):
        return self.cache.ot.value(self.point)

    @property
    def native_value(self):
        return self.value()

    @property
    def extra_state_attributes(self):
        return {"data_role": "read_only_boiler_field", "control_qualified": False,
                "source_protocol": "opentherm", "opentherm_id": self.point.id}


class OtFlagSensor(_OtEntity, BinarySensorEntity):
    def __init__(self, prefix, client, point, product=True):
        super().__init__(prefix, client, product)
        self.point = point
        self._attr_unique_id = unique_id(prefix, point)
        self._attr_translation_key = "ot_" + point.key
        if point.device_class == "problem":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif point.cls in DIAGNOSTIC_CLASSES:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def value(self):
        value = self.cache.ot.value(self.point)
        return None if value is None else bool(value)

    @property
    def is_on(self):
        return self.value()

    @property
    def extra_state_attributes(self):
        return {"data_role": "read_only_boiler_field", "control_qualified": False,
                "source_protocol": "opentherm", "opentherm_id": self.point.id}


class BoilerLinkSensor(_OtEntity, SensorEntity):
    """The stage of the link to an OpenTherm boiler (fw/config/boiler_link), as words."""
    _attr_translation_key = "ot_link"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(STAGES)
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, prefix, client, product=True):
        super().__init__(prefix, client, product)
        self._attr_unique_id = link_unique_id(prefix)

    def value(self):
        document = self.cache.ot.link
        return document["stage"] if document is not None else None

    @property
    def native_value(self):
        return self.value()

    @property
    def extra_state_attributes(self):
        document = self.cache.ot.link
        if document is None:
            return {}
        return {"contact": document["contact"], "limit_c": document["limit"]["c"],
                "limit_source": document["limit"]["source"], "test_passed": document["test"]["passed"],
                "hot_water_present": document["config"]["dhw"], "modulating": document["config"]["modulating"]}


async def _client(hass, entry):
    """(client, add_listener) of a product entry: the running link's, else the retained source; or None."""
    from .v1_boiler_fields import async_retained_source
    state = hass.data[DOMAIN][entry.entry_id]
    runtime = state.get("v1_runtime")
    connection = state.get("v1_connection")
    if runtime is None:
        return None
    if runtime.enabled and connection is not None and connection.client is not None:
        return connection.client, runtime.add_listener
    from .room_plan import has_room_plan
    if not has_room_plan(entry):
        return None
    source = await async_retained_source(hass, entry, state)
    return source, source.add_listener


async def _async_setup(hass, entry, async_add_entities, binary):
    found = await _client(hass, entry)
    if found is None:
        return
    client, add_listener = found
    state = hass.data[DOMAIN][entry.entry_id]
    from .product import is_product
    product = is_product(entry)
    prefix = entry.data[CONF_TOPIC_PREFIX]
    points = [point for point in OWN_POINTS if (point.kind == "bit") == binary]
    entities = {}
    link = []

    def unloading():
        return getattr(state.get("heating_hub"), "closed", False)

    def refresh():
        if unloading():
            return
        cache = client.boiler_fields
        new = []
        for point in points:
            key = unique_id(prefix, point)
            if key not in entities and cache.ot.has_value(point) and cache.link != "ems":
                entities[key] = (OtFlagSensor if binary else OtValueSensor)(prefix, client, point, product)
                new.append(entities[key])
        if (not binary and not link and cache.link == "opentherm" and cache.ot.link is not None
                and cache.ot.link["link"] == "opentherm"):
            link.append(BoilerLinkSensor(prefix, client, product))
            new.append(link[0])
        if new and product:
            from .installation_group import ensure_installation_group
            from .ems_devices import ensure_boiler_device
            group = ensure_installation_group(hass, entry)
            ensure_boiler_device(hass, entry, group)  # the boiler device of the other boiler values
            async_add_entities(new, config_subentry_id=group)
        elif new:
            async_add_entities(new)
        for entity in [*entities.values(), *link]:
            if not entity.added:
                continue
            signature = entity.signature()
            if signature != entity.written:
                entity.written = signature
                entity.async_write_ha_state()

    @callback
    def check_stale(_now=None):
        refresh()  # three missed heartbeats (or offline) make the values unavailable without a new message
    entry.async_on_unload(add_listener(refresh))
    entry.async_on_unload(async_track_time_interval(hass, check_stale, STALE_CHECK))
    refresh()


async def async_setup_sensors(hass, entry, async_add_entities):
    await _async_setup(hass, entry, async_add_entities, False)


async def async_setup_binary_sensors(hass, entry, async_add_entities):
    await _async_setup(hass, entry, async_add_entities, True)
