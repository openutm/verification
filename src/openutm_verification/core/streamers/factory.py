"""Factory for creating air traffic streamers."""

from typing import Literal

from .amqp_streamer import AMQPStreamer
from .flight_blender_streamer import FlightBlenderStreamer
from .null_streamer import NullStreamer
from .protocol import AirTrafficStreamer

TargetType = Literal["flight_blender", "amqp", "none"]


def create_streamer(
    name: TargetType,
    *,
    session_ids: list[str] | None = None,
    **kwargs,
) -> AirTrafficStreamer:
    """Factory function to create streamers by name.

    Args:
        name: Target type - flight_blender, amqp, or none.
        session_ids: Optional list of session UUID strings (for flight_blender).
        **kwargs: Additional streamer-specific arguments.

    Returns:
        An AirTrafficStreamer instance.

    Raises:
        ValueError: If the streamer name is not recognized.
    """
    streamers: dict[str, type] = {
        "flight_blender": FlightBlenderStreamer,
        "amqp": AMQPStreamer,
        "none": NullStreamer,
    }

    if name not in streamers:
        raise ValueError(f"Unknown streamer: {name}. Available: {list(streamers.keys())}")

    return streamers[name].from_config(session_ids=session_ids, **kwargs)
