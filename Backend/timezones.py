"""Timezone utilities and abbreviation handling."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


def _build_abbreviation_map() -> dict[str, str]:
    """Return a mapping of timezone abbreviations to canonical names.

    The mapping is generated from the system's timezone database so most
    abbreviations resolve without manually maintaining a long static list.
    Ambiguous abbreviations are resolved to the first discovered timezone.
    Common North American and European abbreviations are then explicitly
    overridden to their expected regions.
    """
    abbrev_map: dict[str, str] = {}
    conflicts: dict[str, set[str]] = {}
    for tz_name in sorted(available_timezones()):
        zone = ZoneInfo(tz_name)
        for month in (1, 7):  # capture standard and daylight names
            abbr = datetime(2023, month, 1, tzinfo=zone).tzname()
            if abbr:
                abbr = abbr.upper()
                prev = abbrev_map.setdefault(abbr, tz_name)
                if prev != tz_name:
                    conflicts.setdefault(abbr, {prev}).add(tz_name)

    preferred = {
        "CDT": "America/Chicago",
        "CST": "America/Chicago",
        "EDT": "America/New_York",
        "EST": "America/New_York",
        "PDT": "America/Los_Angeles",
        "PST": "America/Los_Angeles",
        "MDT": "America/Denver",
        "MST": "America/Denver",
        "AKDT": "America/Anchorage",
        "AKST": "America/Anchorage",
        "ADT": "America/Halifax",
        "AST": "America/Halifax",
        "NST": "America/St_Johns",
        "NDT": "America/St_Johns",
        "HST": "Pacific/Honolulu",
        "CEST": "Europe/Paris",
        "CET": "Europe/Paris",
        "BST": "Europe/London",
        "IST": "Asia/Kolkata",
        "EEST": "Europe/Athens",
        "EET": "Europe/Athens",
        "WEST": "Europe/Lisbon",
        "WET": "Europe/Lisbon",
        "AEST": "Australia/Sydney",
        "AEDT": "Australia/Sydney",
        "ACST": "Australia/Adelaide",
        "ACDT": "Australia/Adelaide",
        "AWST": "Australia/Perth",
        "NZST": "Pacific/Auckland",
        "NZDT": "Pacific/Auckland",
    }

    overrides: dict[str, str] = {}
    for abbr, zones in conflicts.items():
        overrides[abbr] = preferred.get(abbr, sorted(zones)[0])
    overrides.update(preferred)
    abbrev_map.update(overrides)
    return abbrev_map


# Mapping of common timezone abbreviations to IANA timezone names
ABBREVIATION_MAP = _build_abbreviation_map()


def resolve_timezone(tz: str) -> str:
    """Resolve common timezone abbreviations to IANA timezone names.

    Returns a canonical timezone string usable with ``ZoneInfo``.
    Raises ``ValueError`` if the timezone cannot be resolved.
    """
    canonical = ABBREVIATION_MAP.get(tz.upper(), tz)
    try:
        ZoneInfo(canonical)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {tz}") from exc
    return canonical