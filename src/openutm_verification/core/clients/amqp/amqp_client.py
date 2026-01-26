"""AMQP client for monitoring RabbitMQ queues in verification scenarios."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import pika
import requests
from loguru import logger
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from openutm_verification.core.execution.config_models import get_settings
from openutm_verification.core.execution.scenario_runner import scenario_step


@dataclass
class AMQPSettings:
    """Settings for AMQP connection."""

    url: str = ""
    exchange_name: str = "operational_events"
    exchange_type: str = "direct"
    routing_key: str = "#"  # Flight declaration ID or '#' for all
    queue_name: str = ""
    heartbeat: int = 600
    blocked_connection_timeout: int = 300
    auto_discover: bool = False


@dataclass
class AMQPMessage:
    """Represents a received AMQP message."""

    body: bytes
    routing_key: str
    exchange: str
    delivery_tag: int
    content_type: str | None = None
    correlation_id: str | None = None
    timestamp: str = ""

    def body_str(self) -> str:
        """Decode message body as UTF-8 string."""
        return self.body.decode("utf-8", errors="replace")

    def body_json(self) -> dict[str, Any] | list[Any] | None:
        """Attempt to parse body as JSON, return None if invalid."""
        try:
            data = json.loads(self.body_str())
            # Unpack nested 'body' JSON if present
            if isinstance(data, dict) and "body" in data:
                try:
                    inner_body = json.loads(data["body"])
                    data["body"] = inner_body
                except (json.JSONDecodeError, TypeError):
                    pass
            return data
        except (json.JSONDecodeError, TypeError):
            return None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for reporting."""
        return {
            "routing_key": self.routing_key,
            "exchange": self.exchange,
            "content_type": self.content_type,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "body": self.body_json() or self.body_str(),
        }


@dataclass
class AMQPConsumerState:
    """State for an active AMQP consumer."""

    connection: BlockingConnection | None = None
    channel: BlockingChannel | None = None
    queue_name: str = ""
    messages: list[AMQPMessage] = field(default_factory=list)
    consuming: bool = False
    error: str | None = None
    consumer_thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)


def create_amqp_settings() -> AMQPSettings:
    """Create AMQP settings from configuration or environment.

    Priority: config file > environment variables > defaults.
    """
    settings = AMQPSettings()

    # Try to get from config first
    try:
        config = get_settings()
        if hasattr(config, "amqp") and config.amqp:
            amqp_config = config.amqp
            settings.url = amqp_config.url or settings.url
            settings.exchange_name = amqp_config.exchange_name or settings.exchange_name
            settings.exchange_type = amqp_config.exchange_type or settings.exchange_type
            settings.routing_key = amqp_config.routing_key or settings.routing_key
            settings.queue_name = amqp_config.queue_name or settings.queue_name
    except Exception:
        pass  # Config not available, use env vars

    # Environment overrides
    settings.url = os.environ.get("AMQP_URL", settings.url)
    settings.routing_key = os.environ.get("AMQP_ROUTING_KEY", settings.routing_key)
    settings.queue_name = os.environ.get("AMQP_QUEUE", settings.queue_name)
    settings.auto_discover = os.environ.get("AMQP_AUTO_DISCOVER", "").lower() in (
        "1",
        "true",
        "yes",
    )

    return settings


class AMQPClient:
    """AMQP client for monitoring RabbitMQ queues in verification scenarios.

    This client can be used to:
    - Start background queue monitoring
    - Collect messages during scenario execution
    - Filter and verify received messages

    Example usage in YAML scenarios:
        - step: Start AMQP Queue Monitor
          arguments:
            queue_name: "my-queue"
          background: true
        - step: Submit Telemetry
          arguments:
            duration: 30
        - step: Stop AMQP Queue Monitor
        - step: Get AMQP Messages

    Example usage in Python scenarios:
        amqp_task = asyncio.create_task(
            amqp_client.start_queue_monitor(queue_name="my-queue", duration=60)
        )
        # ... perform other operations ...
        await amqp_task
        messages = await amqp_client.get_received_messages()
    """

    def __init__(self, settings: AMQPSettings):
        self.settings = settings
        self._state = AMQPConsumerState()
        self._lock = threading.Lock()

    def _get_connection_parameters(self) -> pika.URLParameters:
        """Create pika connection parameters from settings."""
        if not self.settings.url:
            raise ValueError("AMQP URL not configured. Set AMQP_URL environment variable or configure 'amqp.url' in config yaml.")

        parameters = pika.URLParameters(self.settings.url)
        parameters.heartbeat = self.settings.heartbeat
        parameters.blocked_connection_timeout = self.settings.blocked_connection_timeout
        return parameters

    def _discover_queues_with_messages(self) -> list[str]:
        """Use RabbitMQ Management API to find queues with messages."""
        if not self.settings.url:
            return []

        parsed = urlparse(self.settings.url)
        username = parsed.username or "guest"
        password = parsed.password or "guest"
        host = parsed.hostname or "localhost"
        vhost = parsed.path.lstrip("/") or "%2f"

        mgmt_ports = [15672, 443, 15671]

        for port in mgmt_ports:
            try:
                scheme = "https" if port == 443 else "http"
                api_url = f"{scheme}://{host}:{port}/api/queues/{vhost}"

                response = requests.get(api_url, auth=(username, password), timeout=5)

                if response.status_code == 200:
                    queues = response.json()
                    queues_with_msgs = [q for q in queues if q.get("messages", 0) > 0 and not q.get("name", "").startswith("amq.gen-")]
                    queues_with_msgs.sort(key=lambda q: q.get("messages", 0), reverse=True)
                    return [q["name"] for q in queues_with_msgs]
            except requests.RequestException:
                continue

        return []

    def _on_message(
        self,
        ch: BlockingChannel,
        method: Any,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:
        """Internal callback for processing received messages."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        msg = AMQPMessage(
            body=body,
            routing_key=method.routing_key,
            exchange=method.exchange or "(default)",
            delivery_tag=method.delivery_tag,
            content_type=properties.content_type,
            correlation_id=properties.correlation_id,
            timestamp=timestamp,
        )

        with self._lock:
            self._state.messages.append(msg)

        logger.debug(f"AMQP message received - routing_key={method.routing_key}, size={len(body)} bytes")

        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def _consumer_loop(
        self,
        queue_name: str | None,
        routing_key: str | None,
        duration: int | None,
    ) -> None:
        """Background consumer loop running in separate thread."""
        connection = None
        try:
            parameters = self._get_connection_parameters()
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            with self._lock:
                self._state.connection = connection
                self._state.channel = channel

            target_queue = queue_name or self.settings.queue_name

            # Auto-discover if enabled
            if self.settings.auto_discover and not target_queue:
                discovered = self._discover_queues_with_messages()
                if discovered:
                    target_queue = discovered[0]
                    logger.info(f"Auto-discovered queue: {target_queue}")

            if target_queue:
                self._state.queue_name = target_queue
                logger.info(f"Consuming from queue: {target_queue}")
            else:
                # Create exclusive queue and bind to exchange
                result = channel.queue_declare(queue="", exclusive=True)
                self._state.queue_name = result.method.queue

                rk = routing_key or self.settings.routing_key
                channel.queue_bind(
                    exchange=self.settings.exchange_name,
                    queue=self._state.queue_name,
                    routing_key=rk,
                )
                logger.info(f"Bound to exchange '{self.settings.exchange_name}' with routing key '{rk}'")

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=self._state.queue_name,
                on_message_callback=self._on_message,
            )

            self._state.consuming = True
            logger.info("AMQP consumer started")

            start_time = time.time()
            while not self._state.stop_event.is_set():
                # Check duration limit
                if duration and (time.time() - start_time) >= duration:
                    logger.info(f"AMQP monitor duration ({duration}s) reached")
                    break

                # Process pending events with short timeout
                connection.process_data_events(time_limit=1)

        except AMQPConnectionError as e:
            logger.error(f"AMQP connection error: {e}")
            self._state.error = str(e)
        except ChannelClosedByBroker as e:
            logger.error(f"Channel closed by broker: {e}")
            self._state.error = str(e)
        except Exception as e:
            logger.error(f"AMQP consumer error: {e}")
            self._state.error = str(e)
        finally:
            self._state.consuming = False
            if connection and connection.is_open:
                try:
                    connection.close()
                except Exception:
                    pass
            logger.info("AMQP consumer stopped")

    @scenario_step("Start AMQP Queue Monitor")
    async def start_queue_monitor(
        self,
        queue_name: str | None = None,
        routing_key: str | None = None,
        duration: int | None = None,
    ) -> dict[str, Any]:
        """Start monitoring an AMQP queue for messages.

        This step starts a background consumer that collects messages from the
        specified queue (or creates an exclusive queue bound to the exchange).

        Args:
            queue_name: Specific queue to monitor. If not provided, creates an
                exclusive queue bound to the exchange with the routing key.
            routing_key: Flight declaration ID to filter messages, or '#' for all.
            duration: Optional duration in seconds to monitor. If not set,
                runs until stop_queue_monitor is called.

        Returns:
            Dictionary with monitoring status and queue name.
        """
        # Clear previous state
        self._state.messages.clear()
        self._state.error = None
        self._state.stop_event.clear()

        # Start consumer in background thread
        self._state.consumer_thread = threading.Thread(
            target=self._consumer_loop,
            args=(queue_name, routing_key, duration),
            daemon=True,
        )
        self._state.consumer_thread.start()

        # Wait briefly for connection to establish
        await asyncio.sleep(0.5)

        if self._state.error:
            raise RuntimeError(f"Failed to start AMQP monitor: {self._state.error}")

        return {
            "status": "started",
            "queue_name": self._state.queue_name or "pending",
            "exchange": self.settings.exchange_name,
            "routing_key": routing_key or self.settings.routing_key,
            "duration": duration,
        }

    @scenario_step("Stop AMQP Queue Monitor")
    async def stop_queue_monitor(self) -> dict[str, Any]:
        """Stop the AMQP queue monitor.

        Returns:
            Dictionary with final status and message count.
        """
        if not self._state.consumer_thread:
            return {"status": "not_running", "message_count": 0}

        # Signal thread to stop
        self._state.stop_event.set()

        # Wait for thread to finish (with timeout)
        self._state.consumer_thread.join(timeout=5.0)

        message_count = len(self._state.messages)
        logger.info(f"AMQP monitor stopped, collected {message_count} messages")

        return {
            "status": "stopped",
            "queue_name": self._state.queue_name,
            "message_count": message_count,
            "error": self._state.error,
        }

    @scenario_step("Get AMQP Messages")
    async def get_received_messages(
        self,
        routing_key_filter: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get messages received by the AMQP monitor.

        Args:
            routing_key_filter: Optional flight declaration ID to filter messages.
            limit: Maximum number of messages to return.

        Returns:
            List of message dictionaries with body, routing_key, etc.
        """
        with self._lock:
            messages = self._state.messages.copy()

        # Apply routing key filter
        if routing_key_filter:
            # Simple pattern matching for AMQP-style wildcards
            import fnmatch

            pattern = routing_key_filter.replace("#", "*").replace(".", "\\.")
            messages = [m for m in messages if fnmatch.fnmatch(m.routing_key, pattern)]

        # Apply limit
        if limit:
            messages = messages[:limit]

        return [m.to_dict() for m in messages]

    @scenario_step("Wait for AMQP Messages")
    async def wait_for_messages(
        self,
        count: int = 1,
        timeout: int = 30,
        routing_key_filter: str | None = None,
    ) -> dict[str, Any]:
        """Wait for a specific number of messages to be received.

        Args:
            count: Number of messages to wait for.
            timeout: Maximum time to wait in seconds.
            routing_key_filter: Optional flight declaration ID to filter messages.

        Returns:
            Dictionary with success status and messages.
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            messages = await self.get_received_messages(routing_key_filter=routing_key_filter)
            if len(messages) >= count:
                return {
                    "success": True,
                    "message_count": len(messages),
                    "messages": messages[:count],
                    "waited_seconds": time.time() - start_time,
                }
            await asyncio.sleep(0.5)

        # Timeout reached
        messages = await self.get_received_messages(routing_key_filter=routing_key_filter)
        return {
            "success": False,
            "message_count": len(messages),
            "messages": messages,
            "timeout": timeout,
            "error": f"Timed out waiting for {count} messages, got {len(messages)}",
        }

    @scenario_step("Clear AMQP Messages")
    async def clear_messages(self) -> dict[str, Any]:
        """Clear the collected messages buffer.

        Returns:
            Dictionary with number of messages cleared.
        """
        with self._lock:
            count = len(self._state.messages)
            self._state.messages.clear()

        logger.info(f"Cleared {count} AMQP messages")
        return {"cleared_count": count}

    @scenario_step("Check AMQP Connection")
    async def check_connection(self) -> dict[str, Any]:
        """Check if AMQP connection can be established.

        Raises:
            RuntimeError: If connection cannot be established.

        Returns:
            Dictionary with connection status and server info.
        """
        try:
            parameters = self._get_connection_parameters()
            connection = pika.BlockingConnection(parameters)

            # Get server version info if available
            version = "unknown"
            try:
                # Access internal implementation for server properties
                if hasattr(connection, "_impl") and hasattr(connection._impl, "server_properties"):
                    server_props = connection._impl.server_properties
                    version_bytes = server_props.get("version", b"unknown")
                    if isinstance(version_bytes, bytes):
                        version = version_bytes.decode("utf-8")
                    elif isinstance(version_bytes, str):
                        version = version_bytes
            except (AttributeError, KeyError):
                pass

            connection.close()

            return {
                "connected": True,
                "server_version": version,
                "url_host": urlparse(self.settings.url).hostname,
            }
        except (AMQPConnectionError, ChannelClosedByBroker) as e:
            raise RuntimeError(f"AMQP connection failed: {e}") from e
        except ValueError as e:
            # Handle configuration errors (e.g., missing URL)
            raise RuntimeError(f"AMQP configuration error: {e}") from e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Stop consumer if running
        if self._state.consumer_thread and self._state.consumer_thread.is_alive():
            self._state.stop_event.set()
            self._state.consumer_thread.join(timeout=2.0)
