import asyncio
import uuid

from loguru import logger
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.scenarios.common import generate_telemetry


class CommonClient:
    @scenario_step("Generate UUID")
    async def generate_uuid(self) -> str:
        """Generates a random UUID."""
        return str(uuid.uuid4())

    @scenario_step("Generate Telemetry")
    async def generate_telemetry_step(
        self,
        config_path: str,
        duration: int = 30,
        reference_time: str | None = None,
    ) -> list[RIDAircraftState]:
        """Generate telemetry states from a trajectory file for scenario reuse."""
        return generate_telemetry(config_path=config_path, duration=duration, reference_time=reference_time)

    @scenario_step("Wait X seconds")
    async def wait(self, duration: int = 5) -> str:
        """Wait for a specified number of seconds."""
        logger.info(f"Waiting for {duration} seconds...")
        await asyncio.sleep(duration)
        logger.info(f"Waited for {duration} seconds.")
        return f"Waited for Flight Blender to process {duration} seconds."
