"""Satispay Business API v1 provider (webhook flow, RSA-SHA256 signing)."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from ..base import BasePaymentProvider, ITransactionStore, InMemoryTransactionStore
from ..models import PaymentRequest, PaymentResult, TransactionData


@dataclass
class SatispayConfig:
    """Configuration for SatispayProvider."""

    key_id: str
    private_key: str  # PEM string
    environment: Literal["sandbox", "live"] = "sandbox"
    server_url: str = ""
    store: ITransactionStore = field(default_factory=InMemoryTransactionStore)


class SatispayProvider(BasePaymentProvider):
    """Payment provider for Satispay Business API v1 (webhook flow).

    Implements the *webhook* flow: ``create_payment`` creates a payment charge
    on Satispay and saves a transaction in the store.  The user pays in the
    Satispay app and Satispay calls the webhook endpoint to confirm.
    ``handle_webhook`` verifies the RSA-SHA256 signature and updates the
    transaction status.
    """

    _SANDBOX_URL = "https://staging.authservices.satispay.com"
    _LIVE_URL = "https://authservices.satispay.com"

    def __init__(self, config: SatispayConfig) -> None:
        self._config = config
        self._base_url = (
            self._SANDBOX_URL
            if config.environment == "sandbox"
            else self._LIVE_URL
        )
        self._store = config.store
        self._private_key = serialization.load_pem_private_key(
            config.private_key.encode(), password=None
        )

    # ------------------------------------------------------------------
    # BasePaymentProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "satispay"

    @property
    def flow(self) -> Literal["webhook"]:
        return "webhook"

    # ------------------------------------------------------------------
    # RSA-SHA256 request signing
    # ------------------------------------------------------------------

    def _sign_request(
        self,
        method: str,
        path: str,
        body: str,
        date: str,
    ) -> str:
        """Build and sign the Satispay authorization header string."""
        body_digest = (
            "SHA-256="
            + hashlib.sha256(body.encode()).digest().hex()
        )
        signing_string = (
            f"(request-target): {method.lower()} {path}\n"
            f"host: {self._base_url.split('://', 1)[-1]}\n"
            f"date: {date}\n"
            f"digest: {body_digest}"
        )
        signature = self._private_key.sign(  # type: ignore[union-attr]
            signing_string.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        signature_b64 = __import__("base64").b64encode(signature).decode()
        return (
            f'Signature keyId="{self._config.key_id}",'
            f'algorithm="rsa-sha256",'
            f'headers="(request-target) host date digest",'
            f'signature="{signature_b64}"'
        )

    async def _api_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload) if payload else ""
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        auth_header = self._sign_request(method, path, body, date)

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                content=body.encode(),
                headers={
                    "Authorization": auth_header,
                    "Content-Type": "application/json",
                    "Date": date,
                    "Digest": (
                        "SHA-256="
                        + hashlib.sha256(body.encode()).hexdigest()
                    ),
                },
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        importo = int(round(request.amount * 100))  # Satispay uses cents
        callback_url = f"{self._config.server_url}/checkout/satispay/webhook"
        payload: dict[str, Any] = {
            "flow": "MATCH_CODE",
            "amount_unit": importo,
            "currency": request.currency,
            "callback_url": callback_url,
            "external_code": request.order_id or str(uuid.uuid4()),
            "redirect_url": request.return_url,
            "metadata": request.metadata,
        }
        data = await self._api_request("POST", "/g_business/v1/payments", payload)
        payment_id: str = data.get("id", str(uuid.uuid4()))

        # Persist to transaction store so webhook can correlate
        await self._store.save(
            payment_id,
            TransactionData(
                payment_id=payment_id,
                order_id=request.order_id,
                amount=request.amount,
                currency=request.currency,
                provider=self.name,
                metadata=request.metadata,
            ),
        )

        redirect_url: str = data.get("redirect_url", request.return_url)
        return PaymentResult(
            payment_id=payment_id,
            status="pending",
            provider=self.name,
            amount=request.amount,
            currency=request.currency,
            redirect_url=redirect_url,
            raw=data,
        )

    async def execute_payment(
        self, payment_id: str, data: dict[str, Any]
    ) -> PaymentResult:
        # Satispay webhook flow; execution is triggered by the user in the app.
        return PaymentResult(
            payment_id=payment_id,
            status="pending",
            provider=self.name,
            raw={"note": "Satispay uses webhook flow; payment is executed by the user in the app."},
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        data = await self._api_request(
            "GET", f"/g_business/v1/payments/{payment_id}"
        )
        status_map = {
            "PENDING": "pending",
            "ACCEPTED": "completed",
            "CANCELED": "failed",
        }
        raw_status: str = data.get("status", "PENDING")
        return PaymentResult(
            payment_id=payment_id,
            status=status_map.get(raw_status, "pending"),  # type: ignore[arg-type]
            provider=self.name,
            raw=data,
        )

    async def refund_payment(
        self, payment_id: str, amount: float | None = None
    ) -> PaymentResult:
        tx = await self._store.get(payment_id)
        refund_amount = int(round(amount * 100)) if amount is not None else None
        payload: dict[str, Any] = {"payment_id": payment_id}
        if refund_amount is not None:
            payload["amount_unit"] = refund_amount
        data = await self._api_request(
            "POST", "/g_business/v1/refunds", payload
        )
        return PaymentResult(
            payment_id=payment_id,
            status="refunded",
            provider=self.name,
            raw=data,
        )

    async def handle_webhook(
        self, body: Any, headers: dict[str, str]
    ) -> PaymentResult:
        if not isinstance(body, dict):
            return PaymentResult(
                payment_id="",
                status="failed",
                provider=self.name,
                raw={"error": "invalid body"},
            )

        payment_id: str = body.get("id", "")
        raw_status: str = body.get("status", "PENDING")
        status_map = {
            "PENDING": "pending",
            "ACCEPTED": "completed",
            "CANCELED": "failed",
        }
        status = status_map.get(raw_status, "pending")
        return PaymentResult(
            payment_id=payment_id,
            status=status,  # type: ignore[arg-type]
            provider=self.name,
            raw=body,
        )

    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult:
        # Satispay uses webhook flow; redirect params only carry the payment ID.
        payment_id: str = query.get("payment_id", "")
        if not payment_id:
            return PaymentResult(
                payment_id="",
                status="pending",
                provider=self.name,
                raw=query,
            )
        return await self.get_payment(payment_id)
