from __future__ import annotations

from typing import Any

import pytest
import requests

from awesome_python_checkout import (
    NexiConfig,
    NexiProvider,
    PaymentRequest,
    PayPalConfig,
    PayPalProvider,
    SatispayConfig,
    SatispayProvider,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_paypal_initiate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(
        self: requests.Session, method: str, url: str, **kwargs: Any
    ) -> FakeResponse:
        assert method == "POST"
        assert url.endswith("/v2/checkout/orders")
        return FakeResponse(
            {
                "id": "PAYPAL-1",
                "links": [{"rel": "approve", "href": "https://paypal.test/approve"}],
            }
        )

    monkeypatch.setattr(requests.Session, "request", fake_request)
    provider = PayPalProvider(PayPalConfig(client_id="id", client_secret="secret"))
    result = provider.initiate(PaymentRequest(amount=12.5, order_id="ord-1"))
    assert result.payment_id == "PAYPAL-1"
    assert result.redirect_url == "https://paypal.test/approve"


def test_nexi_initiate_generates_redirect_url() -> None:
    provider = NexiProvider(NexiConfig(merchant_id="merchant", mac_key="key"))
    result = provider.initiate(
        PaymentRequest(
            amount=10,
            order_id="ord-1",
            return_url="https://ok",
            cancel_url="https://ko",
        )
    )
    assert result.status == "pending"
    assert result.redirect_url is not None
    assert "DispatcherServlet" in result.redirect_url


def test_satispay_verify_from_payload() -> None:
    provider = SatispayProvider(SatispayConfig(key_id="kid", private_key="pem"))
    result = provider.verify("sp-1", {"status": "ACCEPTED"})
    assert result.status == "completed"
