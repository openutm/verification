"""Air traffic streamers module.

Streamers deliver air traffic observations to target systems.
"""

from .factory import TargetType, create_streamer
from .protocol import AirTrafficStreamer, StreamResult

__all__ = [
    "AirTrafficStreamer",
    "StreamResult",
    "TargetType",
    "create_streamer",
]
