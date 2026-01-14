import re
from datetime import datetime


def get_run_timestamp_str(dt: datetime) -> str:
    """Safely format a datetime for use in filenames/directories."""
    # Ensure UTC for consistency if naive? Or just format as is.
    # The requirement is YYYY-MM-DD_HH-MM-SS
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def parse_duration(duration: str | int | float) -> float:
    """
    Parses a duration string (e.g., "5s", "10m", "1h") into seconds.
    If no suffix is provided, defaults to seconds.
    """
    if isinstance(duration, (int, float)):
        return float(duration)

    if not isinstance(duration, str):
        raise ValueError(f"Invalid duration type: {type(duration)}")

    duration = duration.strip().lower()
    if not duration:
        return 0.0

    # Check for simple number string
    try:
        return float(duration)
    except ValueError:
        pass

    # Parse with suffix
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]+)$", duration)
    if not match:
        raise ValueError(f"Invalid duration format: {duration}")

    value, unit = match.groups()
    value = float(value)

    if unit in ("s", "sec", "seconds"):
        return value
    elif unit in ("m", "min", "minutes"):
        return value * 60
    elif unit in ("h", "hr", "hours"):
        return value * 3600
    elif unit in ("d", "day", "days"):
        return value * 86400
    else:
        raise ValueError(f"Unknown time unit: {unit}")
