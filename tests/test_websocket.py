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
        # Block forever after sequence ends
        await asyncio.sleep(1000)
        
    async def send(self, message):
        self.sent_messages.append(json.loads(message))
        
    async def __aiter__(self):
        # Return async iterator that yields nothing (we block in recv after setup)
        while True:
            await asyncio.sleep(1000)
            yield ""


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
        mock_ws = MockWebSocket(connect_response={"type": "error", "message": "Auth failed"})
        
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
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        # Verify URL was constructed correctly with API key
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
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        # Verify subscription was sent
        subscribe_calls = [m for m in mock_ws.sent_messages if m.get("action") == "subscribe"]
        assert len(subscribe_calls) == 1
        assert "2222" in subscribe_calls[0]["symbols"]

    @pytest.mark.asyncio
    async def test_stream_batch_symbol_subscription(self, mock_client):
        """Test that 25 symbols creates 2 subscribe messages."""
        symbols = [str(i) for i in range(25)]  # 25 symbols
        
        # Need enough responses for both subscribe calls
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
                    timeout=0.2
                )
            except asyncio.TimeoutError:
                pass

        # Should have 2 subscribe calls (20 + 5)
        subscribe_calls = [m for m in mock_ws.sent_messages if m.get("action") == "subscribe"]
        assert len(subscribe_calls) == 2
        
        # First batch should have 20 symbols
        assert len(subscribe_calls[0]["symbols"]) == 20
        # Second batch should have 5 symbols
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
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                pass  # Expected

        # Verify subscription was sent
        subscribe_calls = [m for m in mock_ws.sent_messages if m.get("action") == "subscribe"]
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
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        # Verify both symbols in subscription
        subscribe_calls = [m for m in mock_ws.sent_messages if m.get("action") == "subscribe"]
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
