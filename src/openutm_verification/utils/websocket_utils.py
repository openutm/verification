import asyncio
from typing import AsyncGenerator

import arrow
from loguru import logger
from websockets.asyncio.client import ClientConnection


async def receive_messages_for_duration(
    ws_connection: ClientConnection,
    duration_seconds: float,
) -> AsyncGenerator[str | bytes, None]:
    """
    Yields messages from a WebSocket connection for a specified duration.
    Stops when the duration expires or a timeout occurs.
    """
    end_time = arrow.now().shift(seconds=duration_seconds)
    while arrow.now() < end_time:
        remaining_time = (end_time - arrow.now()).total_seconds()
        if remaining_time <= 0:
            break
        try:
            message = await asyncio.wait_for(ws_connection.recv(), timeout=remaining_time)
            yield message
        except asyncio.TimeoutError:
            logger.debug("Timeout waiting for websocket message")
            break
