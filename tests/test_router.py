"""Tests for the FastAPI checkout router."""

from __future__ import annotations

from typing import Any, Literal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from awesome_python_checkout import (
    BasePaymentProvider,
    CheckoutConfigurator,
    PaymentRequest,
    PaymentResult,
)


class _DummyProvider(BasePaymentProvider):
    """Minimal provider for router tests."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            payment_id="pay-router-001",
            status="pending",
            provider=self.name,
            amount=request.amount,
            currency=request.currency,
            redirect_url="https://example.com/redirect",
        )

    async def execute_payment(self, payment_id: str, data: dict[str, Any]) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="completed",
            provider=self.name,
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="completed",
            provider=self.name,
        )

    async def refund_payment(self, payment_id: str, amount: float | None = None) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status="refunded",
            provider=self.name,
        )

    async def handle_webhook(self, body: Any, headers: dict[str, str]) -> PaymentResult:
        return PaymentResult(
            payment_id="pay-router-001",
            status="completed",
            provider=self.name,
        )

    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult:
        return PaymentResult(
            payment_id=query.get("token", "redirect-id"),
            status="completed",
            provider=self.name,
        )


@pytest.fixture()
def client() -> TestClient:
    checkout = CheckoutConfigurator()
    checkout.register_provider(_DummyProvider())
    app = FastAPI()
    app.include_router(checkout.router(), prefix="/checkout")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Route: POST /{provider}
# ---------------------------------------------------------------------------


def test_create_payment_returns_pending(client: TestClient):
    response = client.post(
        "/checkout/dummy",
        json={"amount": 49.99, "currency": "EUR", "order_id": "ORD-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["payment_id"] == "pay-router-001"
    assert data["provider"] == "dummy"


def test_create_payment_unknown_provider_returns_404(client: TestClient):
    response = client.post(
        "/checkout/unknown",
        json={"amount": 1.0, "currency": "EUR"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Route: POST /{provider}/execute
# ---------------------------------------------------------------------------


def test_execute_payment_returns_completed(client: TestClient):
    response = client.post(
        "/checkout/dummy/execute",
        json={"payment_id": "pay-001", "data": {}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


# ---------------------------------------------------------------------------
# Route: GET /{provider}/redirect
# ---------------------------------------------------------------------------


def test_handle_redirect_returns_completed(client: TestClient):
    response = client.get("/checkout/dummy/redirect?token=tok-123")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["payment_id"] == "tok-123"


# ---------------------------------------------------------------------------
# Route: GET /{provider}/{id}
# ---------------------------------------------------------------------------


def test_get_payment_returns_result(client: TestClient):
    response = client.get("/checkout/dummy/pay-router-001")
    assert response.status_code == 200
    data = response.json()
    assert data["payment_id"] == "pay-router-001"
    assert data["status"] == "completed"


# ---------------------------------------------------------------------------
# Route: POST /{provider}/refund
# ---------------------------------------------------------------------------


def test_refund_payment_returns_refunded(client: TestClient):
    response = client.post(
        "/checkout/dummy/refund",
        json={"payment_id": "pay-001", "amount": 10.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "refunded"


# ---------------------------------------------------------------------------
# Route: POST /{provider}/webhook
# ---------------------------------------------------------------------------


def test_handle_webhook_returns_result(client: TestClient):
    response = client.post(
        "/checkout/dummy/webhook",
        json={"event": "payment.completed", "id": "pay-001"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"


# ---------------------------------------------------------------------------
# Unknown provider on all routes
# ---------------------------------------------------------------------------


def test_execute_unknown_provider_returns_404(client: TestClient):
    response = client.post("/checkout/nope/execute", json={"payment_id": "x"})
    assert response.status_code == 404


def test_redirect_unknown_provider_returns_404(client: TestClient):
    response = client.get("/checkout/nope/redirect")
    assert response.status_code == 404


def test_webhook_unknown_provider_returns_404(client: TestClient):
    response = client.post("/checkout/nope/webhook", json={})
    assert response.status_code == 404


def test_refund_unknown_provider_returns_404(client: TestClient):
    response = client.post("/checkout/nope/refund", json={"payment_id": "x"})
    assert response.status_code == 404
