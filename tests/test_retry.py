"""Tests for retry and rate-limit resilience."""

import time
from unittest import mock

import pytest
import requests
import responses
from sahmk import SahmkClient, SahmkError, SahmkRateLimitError


@pytest.fixture
def retry_client():
    """Client with retries enabled and fast backoff for testing."""
    return SahmkClient(
        api_key="shmk_test_retry",
        base_url="https://mock-api.sahmk.sa/api/v1",
        retries=3,
        backoff_factor=0.01,
    )


@pytest.fixture
def no_retry_client():
    """Client with retries disabled."""
    return SahmkClient(
        api_key="shmk_test_noretry",
        base_url="https://mock-api.sahmk.sa/api/v1",
        retries=0,
    )


class TestRetryOnServerError:
    """Tests for retry behavior on 5xx errors."""

    @responses.activate
    def test_retries_on_500_then_succeeds(self, retry_client):
        """Should retry on 500 and succeed when the next attempt returns 200."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(responses.GET, url, body="Server Error", status=500)
        responses.add(responses.GET, url, json={"symbol": "2222", "price": 30.0}, status=200)

        result = retry_client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"
        assert len(responses.calls) == 2

    @responses.activate
    def test_retries_on_502(self, retry_client):
        """Should retry on 502 Bad Gateway."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(responses.GET, url, body="Bad Gateway", status=502)
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        result = retry_client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"

    @responses.activate
    def test_retries_on_503(self, retry_client):
        """Should retry on 503 Service Unavailable."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(responses.GET, url, body="Service Unavailable", status=503)
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        result = retry_client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"

    @responses.activate
    def test_retries_on_504(self, retry_client):
        """Should retry on 504 Gateway Timeout."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(responses.GET, url, body="Gateway Timeout", status=504)
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        result = retry_client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"

    @responses.activate
    def test_exhausts_retries_on_persistent_500(self, retry_client):
        """Should raise after exhausting all retry attempts."""
        url = f"{retry_client.base_url}/quote/2222/"
        for _ in range(4):
            responses.add(responses.GET, url, body="Server Error", status=500)

        with pytest.raises(SahmkError) as exc_info:
            retry_client._request("GET", "/quote/2222/")

        assert exc_info.value.status_code == 500
        assert len(responses.calls) == 4  # 1 initial + 3 retries


class TestNoRetryOnClientError:
    """Tests that 4xx errors (except 429) are NOT retried."""

    @responses.activate
    def test_no_retry_on_400(self, retry_client):
        """400 Bad Request should not be retried."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "BAD_REQUEST", "message": "Bad request"}},
            status=400,
        )

        with pytest.raises(SahmkError) as exc_info:
            retry_client._request("GET", "/quote/2222/")

        assert exc_info.value.status_code == 400
        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_on_401(self, retry_client):
        """401 Unauthorized should not be retried."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "INVALID_API_KEY", "message": "Invalid key"}},
            status=401,
        )

        with pytest.raises(SahmkError):
            retry_client._request("GET", "/quote/2222/")

        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_on_403(self, retry_client):
        """403 Forbidden should not be retried."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "PLAN_LIMIT", "message": "Upgrade required"}},
            status=403,
        )

        with pytest.raises(SahmkError):
            retry_client._request("GET", "/quote/2222/")

        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_on_404(self, retry_client):
        """404 Not Found should not be retried."""
        url = f"{retry_client.base_url}/quote/INVALID/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "INVALID_SYMBOL", "message": "Not found"}},
            status=404,
        )

        with pytest.raises(SahmkError):
            retry_client._request("GET", "/quote/INVALID/")

        assert len(responses.calls) == 1


class TestRetryOnRateLimit:
    """Tests for retry behavior on 429 responses."""

    @responses.activate
    def test_retries_on_429_then_succeeds(self, retry_client):
        """Should retry on 429 and succeed."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "RATE_LIMIT", "message": "Too many"}},
            status=429,
        )
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        result = retry_client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"
        assert len(responses.calls) == 2

    @responses.activate
    def test_respects_retry_after_header(self, retry_client):
        """Should use Retry-After header value for wait time."""
        url = f"{retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "RATE_LIMIT", "message": "Too many"}},
            status=429,
            headers={"Retry-After": "0.01"},
        )
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        with mock.patch("time.sleep") as mock_sleep:
            retry_client._request("GET", "/quote/2222/")
            mock_sleep.assert_called_once_with(0.01)

    @responses.activate
    def test_429_raises_rate_limit_error(self, no_retry_client):
        """429 should raise SahmkRateLimitError (subclass of SahmkError)."""
        url = f"{no_retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "RATE_LIMIT", "message": "Too many"}},
            status=429,
            headers={
                "X-RateLimit-Limit": "5000",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "2026-04-03T00:00:00+03:00",
                "Retry-After": "30",
            },
        )

        with pytest.raises(SahmkRateLimitError) as exc_info:
            no_retry_client._request("GET", "/quote/2222/")

        err = exc_info.value
        assert err.status_code == 429
        assert err.error_code == "RATE_LIMIT"
        assert err.retry_after == 30.0
        assert err.rate_limit == 5000
        assert err.rate_remaining == 0
        assert err.rate_reset == "2026-04-03T00:00:00+03:00"

    @responses.activate
    def test_429_without_headers(self, no_retry_client):
        """429 without rate-limit headers still works."""
        url = f"{no_retry_client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            json={"error": {"code": "RATE_LIMIT", "message": "Too many"}},
            status=429,
        )

        with pytest.raises(SahmkRateLimitError) as exc_info:
            no_retry_client._request("GET", "/quote/2222/")

        err = exc_info.value
        assert err.retry_after is None
        assert err.rate_limit is None
        assert err.rate_remaining is None
        assert err.rate_reset is None


class TestRetryDisabled:
    """Tests that retries=0 disables retry behavior."""

    @responses.activate
    def test_no_retry_when_disabled(self, no_retry_client):
        """With retries=0, failures should not be retried."""
        url = f"{no_retry_client.base_url}/quote/2222/"
        responses.add(responses.GET, url, body="Server Error", status=500)

        with pytest.raises(SahmkError):
            no_retry_client._request("GET", "/quote/2222/")

        assert len(responses.calls) == 1


class TestRetryBackoff:
    """Tests for exponential backoff behavior."""

    @responses.activate
    def test_exponential_backoff_delays(self):
        """Backoff should follow backoff_factor * (2 ** attempt)."""
        client = SahmkClient(
            api_key="test",
            base_url="https://mock-api.sahmk.sa/api/v1",
            retries=3,
            backoff_factor=1.0,
        )
        url = f"{client.base_url}/quote/2222/"
        for _ in range(4):
            responses.add(responses.GET, url, body="Error", status=500)

        with mock.patch("time.sleep") as mock_sleep:
            with pytest.raises(SahmkError):
                client._request("GET", "/quote/2222/")

            delays = [call.args[0] for call in mock_sleep.call_args_list]
            assert delays == [1.0, 2.0, 4.0]

    @responses.activate
    def test_custom_backoff_factor(self):
        """Custom backoff_factor should be respected."""
        client = SahmkClient(
            api_key="test",
            base_url="https://mock-api.sahmk.sa/api/v1",
            retries=2,
            backoff_factor=0.25,
        )
        url = f"{client.base_url}/quote/2222/"
        for _ in range(3):
            responses.add(responses.GET, url, body="Error", status=503)

        with mock.patch("time.sleep") as mock_sleep:
            with pytest.raises(SahmkError):
                client._request("GET", "/quote/2222/")

            delays = [call.args[0] for call in mock_sleep.call_args_list]
            assert delays == [0.25, 0.5]


class TestRetryOnTimeout:
    """Tests for retry_on_timeout behavior."""

    @responses.activate
    def test_retries_on_timeout(self):
        """Should retry on timeout when retry_on_timeout=True."""
        client = SahmkClient(
            api_key="test",
            base_url="https://mock-api.sahmk.sa/api/v1",
            retries=2,
            backoff_factor=0.01,
            retry_on_timeout=True,
        )
        url = f"{client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            body=requests.Timeout("Connection timed out"),
        )
        responses.add(responses.GET, url, json={"symbol": "2222"}, status=200)

        result = client._request("GET", "/quote/2222/")
        assert result["symbol"] == "2222"
        assert len(responses.calls) == 2

    @responses.activate
    def test_no_retry_on_timeout_when_disabled(self):
        """Should not retry on timeout when retry_on_timeout=False."""
        client = SahmkClient(
            api_key="test",
            base_url="https://mock-api.sahmk.sa/api/v1",
            retries=2,
            retry_on_timeout=False,
        )
        url = f"{client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            body=requests.Timeout("Connection timed out"),
        )

        with pytest.raises(SahmkError) as exc_info:
            client._request("GET", "/quote/2222/")

        assert "timed out" in str(exc_info.value)
        assert len(responses.calls) == 1


class TestClientInitRetryParams:
    """Tests for retry parameter initialization."""

    def test_default_retry_params(self):
        """Default retry parameters should be sensible."""
        client = SahmkClient(api_key="test")
        assert client.retries == 3
        assert client.backoff_factor == 0.5
        assert client.retry_on_timeout is True

    def test_custom_retry_params(self):
        """Custom retry parameters should be stored correctly."""
        client = SahmkClient(
            api_key="test",
            retries=5,
            backoff_factor=1.0,
            retry_on_timeout=False,
        )
        assert client.retries == 5
        assert client.backoff_factor == 1.0
        assert client.retry_on_timeout is False

    def test_retries_zero_disables(self):
        """retries=0 should disable retry behavior."""
        client = SahmkClient(api_key="test", retries=0)
        assert client.retries == 0


class TestSahmkRateLimitError:
    """Tests for the SahmkRateLimitError class."""

    def test_inherits_from_sahmk_error(self):
        """Should be a subclass of SahmkError."""
        err = SahmkRateLimitError("test")
        assert isinstance(err, SahmkError)
        assert isinstance(err, Exception)

    def test_default_attributes(self):
        """Should have correct default attributes."""
        err = SahmkRateLimitError("Rate limited")
        assert err.status_code == 429
        assert err.error_code == "RATE_LIMIT"
        assert err.retry_after is None
        assert err.rate_limit is None
        assert err.rate_remaining is None
        assert err.rate_reset is None

    def test_with_metadata(self):
        """Should store all rate-limit metadata."""
        err = SahmkRateLimitError(
            "Rate limited",
            retry_after=30.0,
            rate_limit=5000,
            rate_remaining=0,
            rate_reset="2026-04-03T00:00:00+03:00",
        )
        assert err.retry_after == 30.0
        assert err.rate_limit == 5000
        assert err.rate_remaining == 0
        assert err.rate_reset == "2026-04-03T00:00:00+03:00"

    def test_catchable_as_sahmk_error(self):
        """Should be catchable with except SahmkError."""
        with pytest.raises(SahmkError):
            raise SahmkRateLimitError("test")


class TestNetworkErrors:
    """Tests that non-retriable network errors raise immediately."""

    @responses.activate
    def test_connection_error_not_retried(self):
        """ConnectionError should not be retried (not a timeout)."""
        client = SahmkClient(
            api_key="test",
            base_url="https://mock-api.sahmk.sa/api/v1",
            retries=3,
        )
        url = f"{client.base_url}/quote/2222/"
        responses.add(
            responses.GET, url,
            body=requests.ConnectionError("Connection refused"),
        )

        with pytest.raises(SahmkError) as exc_info:
            client._request("GET", "/quote/2222/")

        assert "Request failed" in str(exc_info.value)
        assert len(responses.calls) == 1
