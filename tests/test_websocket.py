"""Tests for WebSocket streaming functionality."""

import asyncio
import json
import pytest
from unittest import mock

from sahmk import SahmkClient
from sahmk.client import SahmkError, WS_URL


class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(self, recv_sequence=None, connect_response=None):
        self.recv_sequence = recv_sequence or []
        self.connect_response = connect_response or {"type": "connected"}
        self.sent_messages = []
        self.recv_index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def recv(self):
        if self.recv_index == 0:
            self.recv_index += 1
            return json.dumps(self.connect_response)
        elif self.recv_index <= len(self.recv_sequence):
            msg = self.recv_sequence[self.recv_index - 1]
            self.recv_index += 1
            return json.dumps(msg)
        await asyncio.sleep(1000)

    async def send(self, message):
        self.sent_messages.append(json.loads(message))

    async def __aiter__(self):
        while True:
            await asyncio.sleep(1000)
            yield ""


class DisconnectingWebSocket(MockWebSocket):
    """WebSocket that disconnects after delivering some messages."""

    def __init__(
        self,
        recv_sequence=None,
        connect_response=None,
        disconnect_after=0,
        disconnect_error=None,
    ):
        super().__init__(recv_sequence, connect_response)
        self.disconnect_after = disconnect_after
        self.disconnect_error = disconnect_error or ConnectionError("Connection lost")
        self._message_count = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._message_count >= self.disconnect_after:
            raise self.disconnect_error
        self._message_count += 1
        if self._message_count <= len(self.recv_sequence):
            return json.dumps(
                self.recv_sequence[self._message_count - 1]
            )
        raise self.disconnect_error


class TestWebSocketImports:
    """Tests for WebSocket import handling."""

    def test_websocket_missing_import(self, mock_client):
        """Test error when websockets package is not available."""
        with mock.patch.dict("sys.modules", {"websockets": None}):
            with pytest.raises(SahmkError) as exc_info:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        mock_client.stream(["2222"], on_quote=mock.AsyncMock())
                    )
                finally:
                    loop.close()

            assert "websockets package required" in str(exc_info.value)


class TestWebSocketStream:
    """Tests for the stream method."""

    @pytest.mark.asyncio
    async def test_stream_initial_connection_error(self, mock_client):
        """Test handling of connection error during initial connection."""
        mock_ws = MockWebSocket(
            connect_response={"type": "error", "message": "Auth failed"}
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            with pytest.raises(SahmkError) as exc_info:
                await mock_client.stream(["2222"])

            assert "WebSocket error" in str(exc_info.value)
            assert "Auth failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_subscribe_error(self, mock_client):
        """Test handling of subscription error."""
        mock_ws = MockWebSocket(
            recv_sequence=[{"type": "error", "message": "Invalid symbol"}]
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            with pytest.raises(SahmkError) as exc_info:
                await mock_client.stream(["INVALID"])

            assert "Subscribe error" in str(exc_info.value)
            assert "Invalid symbol" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_url_construction(self, mock_client):
        """Test that WebSocket URL includes API key."""
        mock_ws = MockWebSocket()

        connect_mock = mock.MagicMock(return_value=mock_ws)

        with mock.patch("websockets.connect", connect_mock):
            try:
                await asyncio.wait_for(
                    mock_client.stream(["2222"]),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                pass

        call_args = connect_mock.call_args
        url = call_args[0][0]
        assert url.startswith(WS_URL)
        assert f"api_key={mock_client.api_key}" in url

    @pytest.mark.asyncio
    async def test_stream_sends_subscribe_message(self, mock_client):
        """Test that subscription message is sent."""
        mock_ws = MockWebSocket(
            recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}]
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            try:
                await asyncio.wait_for(
                    mock_client.stream(["2222"]),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                pass

        subscribe_calls = [
            m for m in mock_ws.sent_messages if m.get("action") == "subscribe"
        ]
        assert len(subscribe_calls) == 1
        assert "2222" in subscribe_calls[0]["symbols"]

    @pytest.mark.asyncio
    async def test_stream_batch_symbol_subscription(self, mock_client):
        """Test that 25 symbols creates 2 subscribe messages."""
        symbols = [str(i) for i in range(25)]

        mock_ws = MockWebSocket(
            recv_sequence=[
                {"type": "subscribed", "symbols": symbols[:20]},
                {"type": "subscribed", "symbols": symbols[20:]},
            ]
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            try:
                await asyncio.wait_for(
                    mock_client.stream(symbols),
                    timeout=0.2,
                )
            except asyncio.TimeoutError:
                pass

        subscribe_calls = [
            m for m in mock_ws.sent_messages if m.get("action") == "subscribe"
        ]
        assert len(subscribe_calls) == 2

        assert len(subscribe_calls[0]["symbols"]) == 20
        assert len(subscribe_calls[1]["symbols"]) == 5


class TestWebSocketSuccess:
    """Tests for successful WebSocket operations."""

    @pytest.mark.asyncio
    async def test_stream_successful_subscription(self, mock_client):
        """Test successful subscription flow."""
        mock_ws = MockWebSocket(
            recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}]
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            try:
                await asyncio.wait_for(
                    mock_client.stream(["2222"]),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                pass

        subscribe_calls = [
            m for m in mock_ws.sent_messages if m.get("action") == "subscribe"
        ]
        assert len(subscribe_calls) == 1
        assert "2222" in subscribe_calls[0]["symbols"]

    @pytest.mark.asyncio
    async def test_stream_multiple_symbols(self, mock_client):
        """Test streaming multiple symbols."""
        mock_ws = MockWebSocket(
            recv_sequence=[{"type": "subscribed", "symbols": ["2222", "1120"]}]
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            try:
                await asyncio.wait_for(
                    mock_client.stream(["2222", "1120"]),
                    timeout=0.1,
                )
            except asyncio.TimeoutError:
                pass

        subscribe_calls = [
            m for m in mock_ws.sent_messages if m.get("action") == "subscribe"
        ]
        assert len(subscribe_calls) == 1
        assert "2222" in subscribe_calls[0]["symbols"]
        assert "1120" in subscribe_calls[0]["symbols"]


class TestWebSocketConstants:
    """Tests for WebSocket constants."""

    def test_ws_url_constant(self):
        """Test that WS_URL is defined correctly."""
        assert WS_URL == "wss://app.sahmk.sa/ws/v1/stocks/"
        assert WS_URL.startswith("wss://")
        assert WS_URL.endswith("/")


class TestWebSocketReconnect:
    """Tests for auto-reconnect behavior."""

    @pytest.mark.asyncio
    async def test_reconnect_disabled_raises_on_disconnect(self, mock_client):
        """With max_reconnect_attempts=-1, disconnect raises immediately."""
        mock_ws = DisconnectingWebSocket(
            recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
            disconnect_after=0,
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            with pytest.raises(SahmkError) as exc_info:
                await mock_client.stream(
                    ["2222"],
                    max_reconnect_attempts=-1,
                )
            assert "WebSocket disconnected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reconnect_exhausts_max_attempts(self, mock_client):
        """After max_reconnect_attempts, raises SahmkError."""
        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(SahmkError) as exc_info:
                await mock_client.stream(
                    ["2222"],
                    max_reconnect_attempts=3,
                    initial_reconnect_delay=0.01,
                    max_reconnect_delay=0.02,
                )
            assert "reconnection failed after 3 attempts" in str(exc_info.value)

        # 1 initial + 3 retries = 4 connect calls
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_on_disconnect_callback_called(self, mock_client):
        """on_disconnect is called with the disconnect reason."""
        disconnect_reasons = []

        async def on_disconnect(reason):
            disconnect_reasons.append(reason)

        mock_ws = DisconnectingWebSocket(
            recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
            disconnect_after=0,
        )

        with mock.patch("websockets.connect", return_value=mock_ws):
            with pytest.raises(SahmkError):
                await mock_client.stream(
                    ["2222"],
                    on_disconnect=on_disconnect,
                    max_reconnect_attempts=-1,
                )

        assert len(disconnect_reasons) == 1
        assert "Connection lost" in disconnect_reasons[0]

    @pytest.mark.asyncio
    async def test_on_reconnect_callback_called(self, mock_client):
        """on_reconnect is called with the attempt number before reconnecting."""
        reconnect_attempts = []

        async def on_reconnect(attempt):
            reconnect_attempts.append(attempt)

        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(SahmkError):
                await mock_client.stream(
                    ["2222"],
                    on_reconnect=on_reconnect,
                    max_reconnect_attempts=2,
                    initial_reconnect_delay=0.01,
                    max_reconnect_delay=0.02,
                )

        assert reconnect_attempts == [1, 2]

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, mock_client):
        """Verify backoff timing increases exponentially."""
        sleep_durations = []
        original_sleep = asyncio.sleep

        async def mock_sleep(duration):
            sleep_durations.append(duration)
            await original_sleep(0)

        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with mock.patch("asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(SahmkError):
                    await mock_client.stream(
                        ["2222"],
                        max_reconnect_attempts=4,
                        initial_reconnect_delay=1.0,
                        max_reconnect_delay=10.0,
                    )

        assert len(sleep_durations) == 4
        assert sleep_durations[0] == 1.0
        assert sleep_durations[1] == 2.0
        assert sleep_durations[2] == 4.0
        assert sleep_durations[3] == 8.0

    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self, mock_client):
        """Backoff should cap at max_reconnect_delay."""
        sleep_durations = []
        original_sleep = asyncio.sleep

        async def mock_sleep(duration):
            sleep_durations.append(duration)
            await original_sleep(0)

        def make_ws(*args, **kwargs):
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with mock.patch("asyncio.sleep", side_effect=mock_sleep):
                with pytest.raises(SahmkError):
                    await mock_client.stream(
                        ["2222"],
                        max_reconnect_attempts=5,
                        initial_reconnect_delay=1.0,
                        max_reconnect_delay=3.0,
                    )

        assert sleep_durations == [1.0, 2.0, 3.0, 3.0, 3.0]

    @pytest.mark.asyncio
    async def test_unlimited_reconnect_default(self, mock_client):
        """max_reconnect_attempts=0 means unlimited. Verify it keeps trying."""
        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise asyncio.CancelledError("stopping test")
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(asyncio.CancelledError):
                await mock_client.stream(
                    ["2222"],
                    max_reconnect_attempts=0,
                    initial_reconnect_delay=0.01,
                    max_reconnect_delay=0.01,
                )

        assert call_count > 3

    @pytest.mark.asyncio
    async def test_sahmk_error_not_retried(self, mock_client):
        """SahmkError (auth failures etc.) should not trigger reconnect."""
        mock_ws = MockWebSocket(
            connect_response={"type": "error", "message": "Invalid API key"}
        )

        call_count = 0
        original_connect = mock.MagicMock(return_value=mock_ws)

        def counting_connect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_ws

        with mock.patch("websockets.connect", side_effect=counting_connect):
            with pytest.raises(SahmkError) as exc_info:
                await mock_client.stream(
                    ["2222"],
                    max_reconnect_attempts=3,
                    initial_reconnect_delay=0.01,
                )
            assert "Invalid API key" in str(exc_info.value)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_resubscribes_after_reconnect(self, mock_client):
        """After reconnect, all symbols are resubscribed."""
        symbols = ["2222", "1120"]
        all_subscribe_calls = []

        call_count = 0

        class TrackingWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__(
                    recv_sequence=[
                        {"type": "subscribed", "symbols": symbols},
                    ]
                )

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionError("lost connection")

            async def send(self, message):
                data = json.loads(message)
                self.sent_messages.append(data)
                all_subscribe_calls.append(data)

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return TrackingWebSocket()

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(SahmkError):
                await mock_client.stream(
                    symbols,
                    max_reconnect_attempts=1,
                    initial_reconnect_delay=0.01,
                )

        subscribe_msgs = [
            m for m in all_subscribe_calls if m.get("action") == "subscribe"
        ]
        # Should have subscribed on initial + 1 reconnect = 2 subscribe calls
        assert len(subscribe_msgs) == 2
        for msg in subscribe_msgs:
            assert set(msg["symbols"]) == set(symbols)


class TestWebSocketErrorSurfacing:
    """Tests for error surfacing (no silent failures)."""

    @pytest.mark.asyncio
    async def test_error_without_on_error_logs_warning(self, mock_client):
        """Errors without on_error callback should log a warning, not be silent."""

        class ErrorWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__(
                    recv_sequence=[
                        {"type": "subscribed", "symbols": ["2222"]},
                    ]
                )
                self._iter_count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                self._iter_count += 1
                if self._iter_count == 1:
                    return json.dumps(
                        {"type": "error", "message": "rate limit warning"}
                    )
                raise StopAsyncIteration

        mock_ws = ErrorWebSocket()

        with mock.patch("websockets.connect", return_value=mock_ws):
            with mock.patch("sahmk.client.logger") as mock_logger:
                try:
                    await asyncio.wait_for(
                        mock_client.stream(
                            ["2222"],
                            max_reconnect_attempts=-1,
                        ),
                        timeout=0.2,
                    )
                except (asyncio.TimeoutError, SahmkError):
                    pass

                mock_logger.warning.assert_called()
                warning_msg = mock_logger.warning.call_args[0][1]
                assert "rate limit warning" in warning_msg

    @pytest.mark.asyncio
    async def test_error_with_on_error_dispatches(self, mock_client):
        """Errors with on_error callback should be dispatched."""
        errors_received = []

        async def on_error(data):
            errors_received.append(data)

        class ErrorWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__(
                    recv_sequence=[
                        {"type": "subscribed", "symbols": ["2222"]},
                    ]
                )
                self._iter_count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                self._iter_count += 1
                if self._iter_count == 1:
                    return json.dumps(
                        {"type": "error", "message": "something went wrong"}
                    )
                raise StopAsyncIteration

        mock_ws = ErrorWebSocket()

        with mock.patch("websockets.connect", return_value=mock_ws):
            try:
                await asyncio.wait_for(
                    mock_client.stream(
                        ["2222"],
                        on_error=on_error,
                        max_reconnect_attempts=-1,
                    ),
                    timeout=0.2,
                )
            except (asyncio.TimeoutError, SahmkError):
                pass

        assert len(errors_received) == 1
        assert errors_received[0]["message"] == "something went wrong"

    @pytest.mark.asyncio
    async def test_on_disconnect_callback_exception_is_swallowed(self, mock_client):
        """Exceptions in on_disconnect shouldn't crash the reconnect loop."""

        async def bad_on_disconnect(reason):
            raise ValueError("callback crashed")

        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(SahmkError):
                await mock_client.stream(
                    ["2222"],
                    on_disconnect=bad_on_disconnect,
                    max_reconnect_attempts=1,
                    initial_reconnect_delay=0.01,
                )

        # Should have attempted reconnect despite callback crash
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_on_reconnect_callback_exception_is_swallowed(self, mock_client):
        """Exceptions in on_reconnect shouldn't crash the reconnect loop."""

        async def bad_on_reconnect(attempt):
            raise ValueError("callback crashed")

        call_count = 0

        def make_ws(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return DisconnectingWebSocket(
                recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}],
                disconnect_after=0,
            )

        with mock.patch("websockets.connect", side_effect=make_ws):
            with pytest.raises(SahmkError):
                await mock_client.stream(
                    ["2222"],
                    on_reconnect=bad_on_reconnect,
                    max_reconnect_attempts=2,
                    initial_reconnect_delay=0.01,
                )

        assert call_count == 3


class TestStreamConnectionMethod:
    """Tests for the internal _stream_connection method."""

    @pytest.mark.asyncio
    async def test_stream_connection_returns_on_clean_close(self, mock_client):
        """_stream_connection returns normally when server closes cleanly."""

        class CleanCloseWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__(
                    recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}]
                )

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        mock_ws = CleanCloseWebSocket()

        with mock.patch("websockets.connect", return_value=mock_ws):
            await mock_client._stream_connection(
                symbols=["2222"],
                on_quote=mock.AsyncMock(),
            )

    @pytest.mark.asyncio
    async def test_quote_callback_receives_data(self, mock_client):
        """on_quote callback should receive parsed quote data."""
        quotes = []

        async def on_quote(data):
            quotes.append(data)

        quote_data = {
            "type": "quote",
            "symbol": "2222",
            "data": {"price": 32.50},
        }

        class QuoteWebSocket(MockWebSocket):
            def __init__(self):
                super().__init__(
                    recv_sequence=[{"type": "subscribed", "symbols": ["2222"]}]
                )
                self._iter_count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                self._iter_count += 1
                if self._iter_count == 1:
                    return json.dumps(quote_data)
                raise StopAsyncIteration

        mock_ws = QuoteWebSocket()

        with mock.patch("websockets.connect", return_value=mock_ws):
            await mock_client._stream_connection(
                symbols=["2222"],
                on_quote=on_quote,
            )

        assert len(quotes) == 1
        assert quotes[0]["symbol"] == "2222"
        assert quotes[0]["data"]["price"] == 32.50
