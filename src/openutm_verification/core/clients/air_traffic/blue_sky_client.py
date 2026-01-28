from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterable
from uuid import UUID

import arrow
import bluesky as bs
from bluesky.simulation.screenio import ScreenIO
from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    BaseBlueSkyAirTrafficClient,
    BlueSkyAirTrafficSettings,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.models.flight_data_types import (
    FlightObservationSchema,
)
from openutm_verification.utils.paths import relative_path


class BlueSkyClient(BaseBlueSkyAirTrafficClient, BaseBlenderAPIClient):
    """BlueSky client that loads and runs a .scn file and samples aircraft states at 1 Hz."""

    def __init__(self, settings: BlueSkyAirTrafficSettings):
        BaseBlueSkyAirTrafficClient.__init__(self, settings)
        # Initialize BaseBlenderAPIClient with dummy values since we don't use it for HTTP requests here
        # but we inherit from it. Ideally, we should refactor to composition over inheritance.
        BaseBlenderAPIClient.__init__(self, base_url="", credentials={})

    @scenario_step("Generate BlueSky Simulation Air Traffic Data")
    async def generate_bluesky_sim_air_traffic_data(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        """Run BlueSky scenario and sample aircraft state every second.

        Args:
            config_path: Path to .scn scenario file. Defaults to settings.simulation_config_path.
            duration: Simulation duration in seconds. Defaults to settings.simulation_duration_seconds (expected 30).

        Returns:
            list[list[FlightObservationSchema]]: outer list per aircraft (icao_address),
            inner list is time-series sampled at 1 Hz.
        """

        scn_path = config_path or self.settings.simulation_config_path
        duration_s = int(duration or self.settings.simulation_duration_seconds or 30)

        sensor_ids = self.settings.sensor_ids

        try:
            # create a list of UUIDs with at least one UUID if session_ids is empty
            sensor_ids = [UUID(x) for x in sensor_ids] if sensor_ids else [uuid.uuid4()]
        except ValueError as exc:
            logger.error(f"Invalid sensor ID in configuration, it should be a valid UUID: {exc}")
            raise
        current_sensor_id = sensor_ids[0]

        if not scn_path:
            raise ValueError("No scenario path provided. Provide config_path or set settings.simulation_config_path.")

        # ---- Init BlueSky headless ----
        # detached=True prevents UI/event loop from blocking.
        # Use a temporary directory for BlueSky working files to avoid polluting ~/bluesky
        # BlueSky's pathfinder.init() auto-creates required subdirs (scenario, plugins, output, cache)
        with tempfile.TemporaryDirectory(prefix="openutm-bluesky-") as tmp_dir:
            cfg_path = os.path.join(tmp_dir, "settings.cfg")
            bs.init(mode="sim", detached=True, workdir=tmp_dir, configfile=cfg_path)

            # Route console output to stdout (useful for debugging stack commands)
            bs.scr = ScreenDummy()
            now = arrow.now()
            logger.info(f"Initializing BlueSky (headless) and loading scenario: {relative_path(scn_path)} with duration {duration_s}s")

            # ---- Load scenario ----
            # BlueSky scenario files (like scenario/DEMO/bluesky_flight.scn) are typically loaded with IC.
            # NOTE: Use absolute paths if relative paths cause issues inside Docker.
            bs.stack.stack(f"IC {scn_path}")

            # Ensure 1 Hz stepping; FF starts fast-time running mode, but we will still step manually.
            # Some setups work fine with DT 1 and calling bs.sim.step().
            bs.stack.stack("DT 1.0")

            # ---- Sample data at 1 Hz for duration_s seconds ----
            # Store per-aircraft series
            results_by_acid: dict[str, list[FlightObservationSchema]] = {}

            for t in range(1, duration_s + 1):
                # Advance sim by one step (DT=1 sec)
                bs.sim.step()
                timestamp = now.shift(seconds=t)
                timestamp_microseconds = int(timestamp.float_timestamp * 1_000_000)  # microseconds

                # Snapshot traffic arrays
                acids: list[str] = list(getattr(bs.traf, "id", []))
                lats: list[float] = _tolist(getattr(bs.traf, "lat", []))
                lons: list[float] = _tolist(getattr(bs.traf, "lon", []))
                alts: list[float] = _tolist(getattr(bs.traf, "alt", []))

                for i, acid in enumerate(acids):
                    lat = float(lats[i])
                    lon = float(lons[i])
                    alt_m_or_ft = float(alts[i])

                    # BlueSky typically uses meters internally for alt, but some scenarios use FL/ft inputs.
                    # We store altitude_mm as "millimeters"; keep it consistent with your schema.
                    # If alt is actually feet, you can convert here: alt_m = alt_ft * 0.3048
                    altitude_mm = alt_m_or_ft * 1000.0
                    metadata = {"sensor_id": current_sensor_id} if current_sensor_id else {}

                    obs = FlightObservationSchema(
                        lat_dd=lat,
                        lon_dd=lon,
                        altitude_mm=altitude_mm,
                        traffic_source=0,
                        source_type=0,
                        icao_address=acid,
                        timestamp=timestamp_microseconds,
                        metadata=metadata,
                    )
                    results_by_acid.setdefault(acid, []).append(obs)

                    logger.debug(f"{acid:>6} lat={lat:.6f} lon={lon:.6f} alt_mm={altitude_mm:.1f}")

            # Convert dict -> list[list[FlightObservationSchema]] with stable ordering
            return [results_by_acid[acid] for acid in sorted(results_by_acid.keys())]


def _tolist(x: Iterable[float] | object) -> list[float]:
    """Convert numpy arrays / array-likes to a Python list."""
    try:
        return list(x)  # type: ignore[arg-type]
    except TypeError:
        return [float(x)]  # type: ignore[arg-type]


class ScreenDummy(ScreenIO):
    """Dummy screen that prints BlueSky echo/console messages."""

    def echo(self, text: str = "", flags: int = 0) -> None:
        logger.debug(f"BlueSky console: {text}")
