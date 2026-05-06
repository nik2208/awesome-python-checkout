"""Tests for built-in payment providers."""

from __future__ import annotations

import json
from typing import Any

import pytest
import respx
import httpx

from awesome_python_checkout import PaymentRequest
from awesome_python_checkout.providers import (
    NexiConfig,
    NexiProvider,
    PayPalConfig,
    PayPalProvider,
    SatispayConfig,
    SatispayProvider,
)


# ---------------------------------------------------------------------------
# PayPal
# ---------------------------------------------------------------------------


@pytest.fixture()
def paypal_provider() -> PayPalProvider:
    return PayPalProvider(
        PayPalConfig(
            client_id="test-client-id",
            client_secret="test-secret",
            environment="sandbox",
        )
    )


@pytest.fixture()
def payment_request() -> PaymentRequest:
    return PaymentRequest(
        amount=49.99,
        currency="EUR",
        description="Test order",
        return_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        order_id="ORD-001",
    )


@respx.mock
@pytest.mark.asyncio
async def test_paypal_create_payment(paypal_provider: PayPalProvider, payment_request: PaymentRequest):
    # Mock token endpoint
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "test-token"})
    )
    # Mock order creation
    respx.post("https://api-m.sandbox.paypal.com/v2/checkout/orders").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "ORDER-123",
                "status": "CREATED",
                "links": [
                    {"rel": "approve", "href": "https://paypal.com/approve?token=ORDER-123"},
                ],
            },
        )
    )
    result = await paypal_provider.create_payment(payment_request)
    assert result.payment_id == "ORDER-123"
    assert result.status == "pending"
    assert result.redirect_url == "https://paypal.com/approve?token=ORDER-123"
    assert result.provider == "paypal"


@respx.mock
@pytest.mark.asyncio
async def test_paypal_execute_payment(paypal_provider: PayPalProvider):
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    respx.post("https://api-m.sandbox.paypal.com/v2/checkout/orders/ORDER-123/capture").mock(
        return_value=httpx.Response(200, json={"id": "ORDER-123", "status": "COMPLETED"})
    )
    result = await paypal_provider.execute_payment("ORDER-123", {})
    assert result.status == "completed"
    assert result.payment_id == "ORDER-123"


@respx.mock
@pytest.mark.asyncio
async def test_paypal_get_payment(paypal_provider: PayPalProvider):
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    respx.get("https://api-m.sandbox.paypal.com/v2/checkout/orders/ORDER-123").mock(
        return_value=httpx.Response(200, json={"id": "ORDER-123", "status": "COMPLETED"})
    )
    result = await paypal_provider.get_payment("ORDER-123")
    assert result.status == "completed"


@respx.mock
@pytest.mark.asyncio
async def test_paypal_handle_redirect(paypal_provider: PayPalProvider):
    respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok"})
    )
    respx.post("https://api-m.sandbox.paypal.com/v2/checkout/orders/TOK-ABC/capture").mock(
        return_value=httpx.Response(200, json={"id": "TOK-ABC", "status": "COMPLETED"})
    )
    result = await paypal_provider.handle_redirect({"token": "TOK-ABC", "PayerID": "PAYER-1"})
    assert result.status == "completed"
    assert result.payment_id == "TOK-ABC"


@pytest.mark.asyncio
async def test_paypal_handle_redirect_missing_token(paypal_provider: PayPalProvider):
    result = await paypal_provider.handle_redirect({})
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_paypal_handle_webhook_completed(paypal_provider: PayPalProvider):
    body = {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAP-001"}}
    result = await paypal_provider.handle_webhook(body, {})
    assert result.status == "completed"
    assert result.payment_id == "CAP-001"


@pytest.mark.asyncio
async def test_paypal_provider_name_and_flow(paypal_provider: PayPalProvider):
    assert paypal_provider.name == "paypal"
    assert paypal_provider.flow == "redirect"


# ---------------------------------------------------------------------------
# Nexi
# ---------------------------------------------------------------------------


@pytest.fixture()
def nexi_provider() -> NexiProvider:
    return NexiProvider(
        NexiConfig(
            merchant_id="MERCHANT123",
            mac_key="secret-mac-key",
            environment="sandbox",
        )
    )


@pytest.mark.asyncio
async def test_nexi_create_payment(nexi_provider: NexiProvider, payment_request: PaymentRequest):
    result = await nexi_provider.create_payment(payment_request)
    assert result.status == "pending"
    assert result.provider == "nexi"
    assert result.redirect_url is not None
    assert "alias=MERCHANT123" in (result.redirect_url or "")
    assert "mac=" in (result.redirect_url or "")


@pytest.mark.asyncio
async def test_nexi_handle_redirect_ok(nexi_provider: NexiProvider):
    # Build valid MAC
    import hashlib
    fields = {
        "codTrans": "ORD-001",
        "esito": "OK",
        "importo": "4999",
        "divisa": "EUR",
        "data": "20260101",
        "orario": "120000",
        "codAut": "AUTH123",
    }
    mac_string = (
        f"codTrans={fields['codTrans']}"
        f"esito={fields['esito']}"
        f"importo={fields['importo']}"
        f"divisa={fields['divisa']}"
        f"data={fields['data']}"
        f"orario={fields['orario']}"
        f"codAut={fields['codAut']}"
        "secret-mac-key"
    )
    valid_mac = hashlib.sha1(mac_string.encode()).hexdigest()
    fields["mac"] = valid_mac

    result = await nexi_provider.handle_redirect(fields)
    assert result.status == "completed"
    assert result.payment_id == "ORD-001"


@pytest.mark.asyncio
async def test_nexi_handle_redirect_failed_esito(nexi_provider: NexiProvider):
    result = await nexi_provider.handle_redirect({"esito": "KO", "codTrans": "ORD-002", "mac": ""})
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_nexi_handle_redirect_bad_mac(nexi_provider: NexiProvider):
    result = await nexi_provider.handle_redirect(
        {
            "esito": "OK",
            "codTrans": "ORD-003",
            "importo": "100",
            "divisa": "EUR",
            "data": "20260101",
            "orario": "120000",
            "codAut": "AUTH",
            "mac": "bad-mac",
        }
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_nexi_provider_name_and_flow(nexi_provider: NexiProvider):
    assert nexi_provider.name == "nexi"
    assert nexi_provider.flow == "redirect"


# ---------------------------------------------------------------------------
# Satispay
# ---------------------------------------------------------------------------


def _make_rsa_key_pair():
    """Generate a throw-away RSA key pair for testing."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return pem


@pytest.fixture()
def satispay_provider() -> SatispayProvider:
    pem = _make_rsa_key_pair()
    return SatispayProvider(
        SatispayConfig(
            key_id="test-key-id",
            private_key=pem,
            environment="sandbox",
            server_url="https://myapp.com",
        )
    )


@respx.mock
@pytest.mark.asyncio
async def test_satispay_create_payment(satispay_provider: SatispayProvider, payment_request: PaymentRequest):
    respx.post("https://staging.authservices.satispay.com/g_business/v1/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "SAT-PAY-001",
                "status": "PENDING",
                "redirect_url": "https://satispay.com/pay/SAT-PAY-001",
            },
        )
    )
    result = await satispay_provider.create_payment(payment_request)
    assert result.status == "pending"
    assert result.payment_id == "SAT-PAY-001"
    assert result.provider == "satispay"


@respx.mock
@pytest.mark.asyncio
async def test_satispay_get_payment(satispay_provider: SatispayProvider):
    respx.get("https://staging.authservices.satispay.com/g_business/v1/payments/SAT-001").mock(
        return_value=httpx.Response(200, json={"id": "SAT-001", "status": "ACCEPTED"})
    )
    result = await satispay_provider.get_payment("SAT-001")
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_satispay_handle_webhook_accepted(satispay_provider: SatispayProvider):
    body = {"id": "SAT-001", "status": "ACCEPTED"}
    result = await satispay_provider.handle_webhook(body, {})
    assert result.status == "completed"
    assert result.payment_id == "SAT-001"


@pytest.mark.asyncio
async def test_satispay_handle_webhook_pending(satispay_provider: SatispayProvider):
    body = {"id": "SAT-002", "status": "PENDING"}
    result = await satispay_provider.handle_webhook(body, {})
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_satispay_handle_webhook_canceled(satispay_provider: SatispayProvider):
    body = {"id": "SAT-003", "status": "CANCELED"}
    result = await satispay_provider.handle_webhook(body, {})
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_satispay_handle_webhook_invalid_body(satispay_provider: SatispayProvider):
    result = await satispay_provider.handle_webhook("not-a-dict", {})
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_satispay_provider_name_and_flow(satispay_provider: SatispayProvider):
    assert satispay_provider.name == "satispay"
    assert satispay_provider.flow == "webhook"


@pytest.mark.asyncio
async def test_satispay_execute_payment_returns_pending(satispay_provider: SatispayProvider):
    result = await satispay_provider.execute_payment("SAT-001", {})
    assert result.status == "pending"
