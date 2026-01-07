import json
import uuid
from uuid import UUID

import bluesky as bs
from bluesky.simulation import ScreenIO
import numpy as np
from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficSettings,
    BaseAirTrafficAPIClient,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.geo_json_telemetry import (
    GeoJSONAirtrafficSimulator,
)
from openutm_verification.simulator.models.flight_data_types import (
    AirTrafficGeneratorConfiguration,
    FlightObservationSchema,
)


class BlueSkyClient(BaseAirTrafficAPIClient, BaseBlenderAPIClient):

    @scenario_step("Generate BlueSky Simulation Air Traffic Data")
    async def generate_bluesky_sim_airtraffic_data(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        
        # For now ignore any input config. Just generate random traffic using BlueSky simulation dataset
        try:
            bs.init(mode='sim', detached=True)
            bs.scr = ScreenDummy()

            traj_count = 3
            bs.traf.mcre(traj_count, actype="UAV")  # Create n random UAVs
            bs.traf.mcre(traj_count, actype="B744")  # Create n random B744s
            # bs.ref.area.set_boundbox(*self._get_bound_box())

            # set simulation bounding box

            # run the simulation. Hopefully BlueSky will be able to generate routes data itself. Will need to check once we get it running.
            for acid in bs.traf.id:
                bs.stack.stack(f'ORIG {acid} EGLL;'
                    f'ADDWPT {acid} BPK FL60;'
                    f'ADDWPT {acid} TOTRI FL107;'
                    f'ADDWPT {acid} MATCH FL115;'
                    f'ADDWPT {acid} BRAIN FL164;'
                    f'VNAV {acid} ON')

            bs.stack.stack('DT 1;FF')

            t_max = 4000

            ntraf = bs.traf.ntraf
            n_steps = int(t_max + 1)
            t = np.linspace(0, t_max, n_steps)

            # allocate some empty arrays for the results
            results: list[list[FlightObservationSchema]] = []

            # iteratively simulate the traffic
            for i in range(n_steps):
                bs.sim.step()
                #             bs.traf.tas]
                idx = bs.traf.id2idx(bs.traf.id)
                obj: FlightObservationSchema = FlightObservationSchema(
                    lat_dd=float(bs.traf.lat[idx]),
                    lon_dd=float(bs.traf.lon[idx]),
                    altitude_mm=float(bs.traf.alt[idx]),
                    traffic_source=0,
                    source_type=0,
                    icao_address="",
                    timestamp=0,
                    metadata={},
                )
                id = bs.traf.id
                results.append([obj])

            return results

        except Exception as exc:
            raise exc
        finally:
            return list()


    def _get_bound_box(self) -> tuple[float, float, float, float]:
        """Get bounding box from the simulation config GeoJSON data.

        Returns:
            A tuple representing the bounding box (min_lon, min_lat, max_lon, max_lat).
        """
        return (0.0, 0.0, 0.0, 0.0)


class ScreenDummy(ScreenIO):
    """
    Dummy class for the screen. Inherits from ScreenIO to make sure all the
    necessary methods are there. This class is there to reimplement the echo
    method so that console messages are printed.
    """
    def echo(self, text='', flags=0):
        """Just print echo messages"""
        print("BlueSky console:", text)

