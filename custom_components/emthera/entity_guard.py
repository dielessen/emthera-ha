"""Whether a Home Assistant entity of ours is really added (nothing heavy imported here).

Home Assistant sets ``entity_id`` first and then, for an entity that is disabled in the entity registry (or whose id is
taken, or whose registry write failed), aborts adding it: ``entity_id`` stays set and ``hass`` becomes None.
``async_write_ha_state`` on such an entity raises RuntimeError("Attribute hass is None"), which would stop whatever
updates it (a loop over entities, an MQTT handler). A test of ``entity_id`` alone does not tell the two apart.
"""


def is_added(entity):
    """True only when Home Assistant added the entity: it has its ``hass`` and its ``entity_id``."""
    return getattr(entity, "hass", None) is not None and getattr(entity, "entity_id", None) is not None
