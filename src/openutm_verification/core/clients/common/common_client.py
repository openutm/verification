import asyncio
import uuid

from loguru import logger

from openutm_verification.core.execution.scenario_runner import scenario_step


class CommonClient:
    @scenario_step("Generate UUID")
    async def generate_uuid(self) -> str:
        """Generates a random UUID."""
        return str(uuid.uuid4())

    @scenario_step("Wait X seconds")
    async def wait(self, duration: int = 5) -> str:
        """Wait for a specified number of seconds."""
        logger.info(f"Waiting for {duration} seconds...")
        await asyncio.sleep(duration)
        logger.info(f"Waited for {duration} seconds.")
        return f"Waited for Flight Blender to process {duration} seconds."
