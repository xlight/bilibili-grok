"""Health check endpoint for Bilibili Grok."""

import asyncio
import signal
import time
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiohttp import web


@dataclass
class HealthStatus:
    """Health status of the application."""

    status: str = "healthy"
    uptime_seconds: float = 0
    timestamp: str = ""
    components: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp,
            "components": self.components,
        }


class HealthCheck:
    """Health check handler with component status."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.host = host
        self.port = port
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._start_time = time.time()
        self._shutdown_event = asyncio.Event()
        self._component_checks: dict[str, Callable] = {}

    def register_component(self, name: str, check_fn: Callable[[], Any]):
        """Register a component health check function.

        Args:
            name: Component name
            check_fn: Async function that returns component status dict
        """
        self._component_checks[name] = check_fn

    async def _check_components(self) -> dict:
        """Check all registered components."""
        results = {}

        for name, check_fn in self._component_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    result = check_fn()
                results[name] = result
            except Exception as e:
                results[name] = {"status": "unhealthy", "error": str(e)}

        return results

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check HTTP handler."""
        components = await self._check_components()

        overall_status = "healthy"
        for comp_status in components.values():
            if isinstance(comp_status, dict) and comp_status.get("status") == "unhealthy":
                overall_status = "degraded"
                break

        status = HealthStatus(
            status=overall_status,
            uptime_seconds=time.time() - self._start_time,
            timestamp=datetime.utcnow().isoformat() + "Z",
            components=components,
        )

        return web.json_response(
            status.to_dict(),
            status=200 if overall_status == "healthy" else 503,
        )

    async def start(self):
        """Start the health check server."""
        self._app = web.Application()
        self._app.router.add_get("/health", self.health_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

    async def stop(self):
        """Stop the health check server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._app = None

    @property
    def is_running(self) -> bool:
        return self._runner is not None


class GracefulShutdown:
    """Handle graceful shutdown on SIGTERM/SIGINT."""

    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._callbacks: list[Callable] = []
        self._original_handlers: dict = {}

    def register_callback(self, callback: Callable):
        """Register a callback to be called on shutdown."""
        self._callbacks.append(callback)

    def _signal_handler(self, signum: int, frame: types.FrameType | None) -> None:
        """Handle shutdown signal."""
        print(f"Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self._shutdown())

    async def _shutdown(self):
        """Perform graceful shutdown."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                print(f"Error during shutdown callback: {e}")

        self._shutdown_event.set()

    def setup(self) -> None:
        """Setup signal handlers."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._original_handlers[sig] = signal.signal(sig, self._signal_handler)

    def cleanup(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()
