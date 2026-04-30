"""User-friendly YAML/JSON scenario definition for BlueSky (.scn) files.

Instead of writing raw BlueSky stack commands, users can define scenarios in a
structured YAML or JSON format and have them converted to .scn files automatically.

Example YAML scenario::

    name: "A1 Head-On Approach"
    description: "ASTM F3442 Category A1 head-on scenario"
    display:
      pan: [53.5200, -113.5750]
      trails: true
      reso: false
      rtf: 10
    areas:
      - name: EDM_A1_BOX
        color: [0, 255, 0]
        bounds:
          - [53.5100, -113.6100]
          - [53.5100, -113.5400]
          - [53.5300, -113.5400]
          - [53.5300, -113.6100]
    aircraft:
      - callsign: INTA1
        type: C172
        lat: 53.5200
        lon: -113.5500
        heading: 270
        altitude_ft: 400
        speed_kts: 87
        waypoints:
          - [53.5200, -113.5750]
          - [53.5200, -113.6000]
    hold_time: "00:02:00.00"
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Regex for BlueSky timed stack commands: HH:MM:SS.SS
# Hours: any non-negative integer; minutes/seconds: 00–59; fractional: exactly 2 digits.
_BLUESKY_TIME_RE = re.compile(r"^\d+:([0-5]\d):([0-5]\d)\.\d{2}$")


class BlueSkyArea(BaseModel):
    """A named polygon area displayed in the BlueSky visualizer."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Name of the area polygon (used in POLY command)")
    bounds: list[Annotated[list[float], Field(min_length=2, max_length=2)]] = Field(
        ...,
        min_length=3,
        description="List of [lat, lon] coordinate pairs forming the polygon boundary",
    )
    color: Annotated[list[int], Field(min_length=3, max_length=3)] = Field(
        default=[0, 255, 0],
        description="RGB color for the polygon as [R, G, B] with values 0–255",
    )

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: list[int]) -> list[int]:
        for channel in v:
            if not (0 <= channel <= 255):
                raise ValueError(f"Color channel value {channel} must be between 0 and 255")
        return v


class BlueSkyDisplaySettings(BaseModel):
    """Viewport and display configuration for BlueSky."""

    model_config = ConfigDict(extra="forbid")

    pan: Annotated[list[float], Field(min_length=2, max_length=2)] | None = Field(
        default=None,
        description="Center the view on [lat, lon]",
    )
    trails: bool = Field(default=True, description="Show aircraft trails")
    reso: bool = Field(default=False, description="Enable resolution advisories")
    rtf: int = Field(default=10, ge=1, description="Real-time factor (simulation speed multiplier)")


class BlueSkyAircraft(BaseModel):
    """A single aircraft to be created and flown in the BlueSky scenario."""

    model_config = ConfigDict(extra="forbid")

    callsign: str = Field(..., description="Aircraft callsign / ACID (e.g. INTA1)")
    type: str = Field(..., description="Aircraft type code (e.g. C172, B744, P28A)")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Initial latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Initial longitude in decimal degrees")
    heading: float = Field(..., ge=0.0, le=360.0, description="Initial true heading in degrees")
    altitude_ft: float = Field(..., ge=0.0, description="Initial altitude in feet")
    speed_kts: float = Field(..., ge=0.0, description="Initial airspeed in knots")
    start_time: str = Field(default="00:00:00.00", description="Simulation time to create this aircraft (HH:MM:SS.SS)")
    waypoints: list[Annotated[list[float], Field(min_length=2, max_length=2)]] = Field(
        default_factory=list,
        description="Ordered list of [lat, lon] waypoints for the aircraft to follow",
    )

    @field_validator("callsign")
    @classmethod
    def _validate_callsign(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("callsign must not be empty")
        return v

    @field_validator("start_time")
    @classmethod
    def _validate_time_format(cls, v: str) -> str:
        if not _BLUESKY_TIME_RE.match(v):
            raise ValueError(f"start_time '{v}' must be in HH:MM:SS.SS format with minutes and seconds in range 00–59")
        return v


class BlueSkyScenarioDefinition(BaseModel):
    """User-friendly definition of a BlueSky simulation scenario.

    This model can be serialised to/from YAML or JSON and converted to the
    BlueSky ``.scn`` stack-command format via :meth:`to_scn`.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Human-readable name for this scenario")
    description: str = Field(default="", description="Optional longer description of the scenario")
    display: BlueSkyDisplaySettings = Field(default_factory=BlueSkyDisplaySettings)
    areas: list[BlueSkyArea] = Field(default_factory=list, description="Polygon areas to display")
    aircraft: list[BlueSkyAircraft] = Field(..., min_length=1, description="List of aircraft to simulate")
    hold_time: str = Field(
        default="00:02:00.00",
        description="Simulation time at which the HOLD command is issued to stop the run (HH:MM:SS.SS)",
    )

    @field_validator("hold_time")
    @classmethod
    def _validate_hold_time(cls, v: str) -> str:
        if not _BLUESKY_TIME_RE.match(v):
            raise ValueError(f"hold_time '{v}' must be in HH:MM:SS.SS format with minutes and seconds in range 00–59")
        return v

    @model_validator(mode="after")
    def _callsigns_unique(self) -> "BlueSkyScenarioDefinition":
        seen: set[str] = set()
        for ac in self.aircraft:
            if ac.callsign in seen:
                raise ValueError(f"Duplicate aircraft callsign: {ac.callsign}")
            seen.add(ac.callsign)
        return self

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_scn(self) -> str:
        """Render this scenario definition as a BlueSky ``.scn`` file string.

        Returns:
            str: The complete text content of a BlueSky ``.scn`` file.
        """
        lines: list[str] = []

        # Header comment
        lines.append(f"# {self.name}")
        if self.description:
            for desc_line in self.description.splitlines():
                lines.append(f"# {desc_line}")
        lines.append("")

        # Polygon areas
        for area in self.areas:
            coord_str = " ".join(f"{lat},{lon}" for lat, lon in area.bounds)
            lines.append(f"00:00:00.00>POLY {area.name} {coord_str}")
            r, g, b = area.color
            lines.append(f"00:00:00.00>COLOR {area.name} {r},{g},{b}")
            lines.append("")

        # Display / viewport settings
        disp = self.display
        lines.append(f"00:00:00.00>TRAILS {'ON' if disp.trails else 'OFF'}")
        lines.append(f"00:00:00.00>RESO {'ON' if disp.reso else 'OFF'}")
        lines.append(f"00:00:00.00>RTF {disp.rtf}")
        if disp.pan is not None:
            lat_pan, lon_pan = disp.pan
            lines.append(f"00:00:00.00>PAN {_fmt_coord(lat_pan)},{_fmt_coord(lon_pan)}")
        lines.append("00:00:00.00>-")
        lines.append("")

        # Aircraft
        for ac in self.aircraft:
            alt_str = _format_altitude(ac.altitude_ft)
            lines.append(f"# {ac.callsign}: {ac.type}, hdg {_fmt_num(ac.heading)}° alt {alt_str} spd {_fmt_num(ac.speed_kts)} kts")
            lines.append(
                f"{ac.start_time}>CRE {ac.callsign},{ac.type},"
                f"{_fmt_coord(ac.lat)},{_fmt_coord(ac.lon)},"
                f"{_fmt_num(ac.heading)},{_fmt_num(ac.altitude_ft)},{_fmt_num(ac.speed_kts)}"
            )
            for wpt_lat, wpt_lon in ac.waypoints:
                lines.append(f"{ac.start_time}>{ac.callsign} ADDWPT {_fmt_coord(wpt_lat)},{_fmt_coord(wpt_lon)}")
            lines.append("")

        # Hold command
        lines.append(f"{self.hold_time}>HOLD")

        return "\n".join(lines) + "\n"

    def write_scn(self, path: str | Path) -> Path:
        """Write the rendered ``.scn`` content to *path*.

        Args:
            path: Destination file path.  Parent directories are created if necessary.

        Returns:
            Path: The resolved path that was written.
        """
        dest = Path(path).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(self.to_scn(), encoding="utf-8")
        return dest

    def write_temp_scn(self) -> str:
        """Write the scenario to a temporary ``.scn`` file and return its path.

        The caller is responsible for deleting the file when done (or using a
        :class:`tempfile.TemporaryDirectory` context).

        Returns:
            str: Absolute path to the temporary ``.scn`` file.
        """
        fd, tmp_path = tempfile.mkstemp(prefix="openutm-bluesky-", suffix=".scn")
        os.close(fd)
        Path(tmp_path).write_text(self.to_scn(), encoding="utf-8")
        return tmp_path


# ------------------------------------------------------------------
# Factory / loader helpers
# ------------------------------------------------------------------


def load_bluesky_scenario(path: str | Path) -> BlueSkyScenarioDefinition:
    """Load a :class:`BlueSkyScenarioDefinition` from a YAML or JSON file.

    The file format is detected from the file extension:
    * ``.yaml`` / ``.yml`` → YAML
    * ``.json`` → JSON

    Args:
        path: Path to the YAML or JSON scenario definition file.

    Returns:
        BlueSkyScenarioDefinition: The parsed scenario definition.

    Raises:
        ValueError: If the file extension is not recognised.
        FileNotFoundError: If the file does not exist.
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"BlueSky scenario file not found: {p}")

    suffix = p.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        with p.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    elif suffix == ".json":
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        raise ValueError(f"Unsupported file extension '{suffix}' for BlueSky scenario definition. Use .yaml, .yml, or .json")

    return BlueSkyScenarioDefinition.model_validate(data)


def resolve_scn_path(config_path: str) -> tuple[str, bool]:
    """Resolve a config path to a ``.scn`` file path.

    If *config_path* points to a YAML or JSON file, converts it to a temporary
    ``.scn`` file and returns the temp path along with ``True`` (indicating the
    caller owns the temp file).

    If *config_path* already points to a ``.scn`` (or any other extension), it
    is returned unchanged with ``False``.

    Args:
        config_path: Path to a ``.scn``, ``.yaml``, ``.yml``, or ``.json`` file.

    Returns:
        tuple[str, bool]: ``(resolved_scn_path, is_temp)`` where *is_temp* is
        ``True`` when a temporary file was created and should be cleaned up.
    """
    suffix = Path(config_path).suffix.lower()
    if suffix in {".yaml", ".yml", ".json"}:
        definition = load_bluesky_scenario(config_path)
        tmp_path = definition.write_temp_scn()
        return tmp_path, True
    return config_path, False


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _format_altitude(altitude_ft: float) -> str:
    """Format an altitude value for display in comments."""
    if altitude_ft >= 1000 and altitude_ft % 100 == 0:
        fl = int(altitude_ft // 100)
        return f"FL{fl:03d}"
    return f"{altitude_ft:.0f} ft"


def _fmt_num(v: float) -> str:
    """Render a float as an integer string when it is a whole number, otherwise as-is.

    This keeps BlueSky stack commands clean: ``270`` instead of ``270.0``.
    """
    if v == int(v):
        return str(int(v))
    return str(v)


def _fmt_coord(v: float) -> str:
    """Render a latitude or longitude to 4 decimal places.

    This matches the precision convention used in the existing ``.scn`` files
    in the ``config/`` directory (e.g. ``53.5200,-113.5500``).
    """
    return f"{v:.4f}"
