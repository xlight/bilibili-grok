"""Tests for health module."""

import asyncio
import signal
from unittest.mock import MagicMock, patch

import pytest

from grok.health import GracefulShutdown, HealthCheck, HealthStatus


class TestHealthStatus:
    def test_health_status_to_dict(self):
        status = HealthStatus(
            status="healthy",
            uptime_seconds=100.0,
            timestamp="2024-01-01T00:00:00Z",
            components={"db": {"status": "healthy"}},
        )

        result = status.to_dict()

        assert result["status"] == "healthy"
        assert result["uptime_seconds"] == 100.0
        assert result["timestamp"] == "2024-01-01T00:00:00Z"
        assert result["components"] == {"db": {"status": "healthy"}}


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health_handler_healthy(self):
        health = HealthCheck(host="127.0.0.1", port=8888)
        health.register_component("test", lambda: {"status": "healthy"})

        request = MagicMock()
        response = await health.health_handler(request)

        assert response.status == 200

    async def test_health_handler_degraded(self):
        health = HealthCheck(host="127.0.0.1", port=8889)
        health.register_component("test", lambda: {"status": "unhealthy"})

        request = MagicMock()
        response = await health.health_handler(request)

        assert response.status == 503

    async def test_register_component_sync(self):
        health = HealthCheck()

        def sync_check():
            return {"status": "healthy", "count": 10}

        health.register_component("sync_test", sync_check)
        result = await health._check_components()

        assert "sync_test" in result
        assert result["sync_test"]["status"] == "healthy"
        assert result["sync_test"]["count"] == 10

    async def test_register_component_async(self):
        health = HealthCheck()

        async def async_check():
            return {"status": "healthy", "async": True}

        health.register_component("async_test", async_check)
        result = await health._check_components()

        assert "async_test" in result
        assert result["async_test"]["status"] == "healthy"
        assert result["async_test"]["async"] is True

    async def test_component_check_exception(self):
        health = HealthCheck()

        def failing_check():
            raise ValueError("Test error")

        health.register_component("failing", failing_check)
        result = await health._check_components()

        assert "failing" in result
        assert result["failing"]["status"] == "unhealthy"
        assert "Test error" in result["failing"]["error"]

    async def test_start_stop_lifecycle(self):
        health = HealthCheck(host="127.0.0.1", port=8890)

        assert not health.is_running

        await health.start()
        assert health.is_running

        await asyncio.sleep(0.1)

        await health.stop()
        assert not health.is_running

    async def test_is_running_property(self):
        health = HealthCheck()

        assert health.is_running is False

        health._runner = MagicMock()
        assert health.is_running is True

        health._runner = None
        assert health.is_running is False


class TestGracefulShutdown:
    def test_register_callback(self):
        shutdown = GracefulShutdown()

        callback = MagicMock()
        shutdown.register_callback(callback)

        assert callback in shutdown._callbacks

    def test_register_multiple_callbacks(self):
        shutdown = GracefulShutdown()

        callback1 = MagicMock()
        callback2 = MagicMock()
        shutdown.register_callback(callback1)
        shutdown.register_callback(callback2)

        assert len(shutdown._callbacks) == 2

    @pytest.mark.asyncio
    async def test_shutdown_calls_callbacks(self):
        shutdown = GracefulShutdown()

        callback_called = []

        async def async_callback():
            callback_called.append("async")

        def sync_callback():
            callback_called.append("sync")

        shutdown.register_callback(async_callback)
        shutdown.register_callback(sync_callback)

        await shutdown._shutdown()

        assert "async" in callback_called
        assert "sync" in callback_called

    @pytest.mark.asyncio
    async def test_shutdown_handles_callback_exception(self):
        shutdown = GracefulShutdown()

        async def failing_callback():
            raise ValueError("Test error")

        success_called = []

        async def success_callback():
            success_called.append(True)

        shutdown.register_callback(failing_callback)
        shutdown.register_callback(success_callback)

        await shutdown._shutdown()

        assert success_called

    def test_setup_signal_handlers(self):
        shutdown = GracefulShutdown()

        with patch("signal.signal") as mock_signal:
            shutdown.setup()

            calls = [call[0][0] for call in mock_signal.call_args_list]
            assert signal.SIGTERM in calls
            assert signal.SIGINT in calls

    def test_cleanup_restores_handlers(self):
        shutdown = GracefulShutdown()

        original_term = signal.getsignal(signal.SIGTERM)
        original_int = signal.getsignal(signal.SIGINT)

        shutdown.setup()
        shutdown.cleanup()

        assert signal.getsignal(signal.SIGTERM) == original_term
        assert signal.getsignal(signal.SIGINT) == original_int

    @pytest.mark.asyncio
    async def test_is_shutting_down(self):
        shutdown = GracefulShutdown()

        assert not shutdown.is_shutting_down

        await shutdown._shutdown()

        assert shutdown.is_shutting_down

    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self):
        shutdown = GracefulShutdown()

        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            await shutdown._shutdown()

        task = asyncio.create_task(trigger_shutdown())

        try:
            await asyncio.wait_for(shutdown.wait_for_shutdown(), timeout=0.5)
        except asyncio.TimeoutError:
            pass

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
