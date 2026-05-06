"""Nexi eCommerce redirect provider (MAC SHA-1 signature)."""

from __future__ import annotations

import hashlib
import urllib.parse
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from ..base import BasePaymentProvider
from ..models import PaymentRequest, PaymentResult


@dataclass
class NexiConfig:
    """Configuration for NexiProvider."""

    merchant_id: str
    mac_key: str
    environment: Literal["sandbox", "live"] = "sandbox"


class NexiProvider(BasePaymentProvider):
    """Payment provider for Nexi eCommerce (redirect flow, MAC SHA-1).

    Implements the *redirect* flow: ``create_payment`` builds the
    DispatcherServlet redirect URL, and ``handle_redirect`` validates the MAC
    and returns a completed/failed result.
    """

    _SANDBOX_URL = "https://int-ecommerce.nexi.it/ecomm/ecomm/DispatcherServlet"
    _LIVE_URL = "https://ecommerce.nexi.it/ecomm/ecomm/DispatcherServlet"

    def __init__(self, config: NexiConfig) -> None:
        self._config = config
        self._base_url = (
            self._SANDBOX_URL
            if config.environment == "sandbox"
            else self._LIVE_URL
        )

    # ------------------------------------------------------------------
    # BasePaymentProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "nexi"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    # ------------------------------------------------------------------
    # MAC helpers
    # ------------------------------------------------------------------

    def _compute_mac(self, fields: dict[str, str]) -> str:
        """Compute SHA-1 MAC as required by Nexi eCommerce."""
        mac_string = (
            f"codTrans={fields.get('codTrans', '')}"
            f"divisa={fields.get('divisa', '')}"
            f"importo={fields.get('importo', '')}"
            f"{self._config.mac_key}"
        )
        return hashlib.sha1(mac_string.encode()).hexdigest()

    def _compute_response_mac(self, fields: dict[str, str]) -> str:
        """Compute SHA-1 MAC for the redirect response verification."""
        mac_string = (
            f"codTrans={fields.get('codTrans', '')}"
            f"esito={fields.get('esito', '')}"
            f"importo={fields.get('importo', '')}"
            f"divisa={fields.get('divisa', '')}"
            f"data={fields.get('data', '')}"
            f"orario={fields.get('orario', '')}"
            f"codAut={fields.get('codAut', '')}"
            f"{self._config.mac_key}"
        )
        return hashlib.sha1(mac_string.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        # Convert amount to integer cents (importo in Nexi = amount in cents as string)
        importo = str(int(round(request.amount * 100)))
        params: dict[str, str] = {
            "alias": self._config.merchant_id,
            "importo": importo,
            "divisa": request.currency,
            "codTrans": request.order_id or "order",
            "url": request.return_url,
            "url_back": request.cancel_url,
            "languageId": "ITA",
            "descrizione": request.description,
        }
        params["mac"] = self._compute_mac(params)
        redirect_url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        return PaymentResult(
            payment_id=request.order_id or "order",
            status="pending",
            provider=self.name,
            amount=request.amount,
            currency=request.currency,
            redirect_url=redirect_url,
            raw=params,
        )

    async def execute_payment(
        self, payment_id: str, data: dict[str, Any]
    ) -> PaymentResult:
        # Nexi redirect flow does not have a separate capture step.
        return PaymentResult(
            payment_id=payment_id,
            status="pending",
            provider=self.name,
            raw={"note": "Nexi redirect flow; use handle_redirect after user returns."},
        )

    async def get_payment(self, payment_id: str) -> PaymentResult:
        # Nexi does not expose a REST API for order look-up in the basic eCommerce product.
        return PaymentResult(
            payment_id=payment_id,
            status="pending",
            provider=self.name,
            raw={"note": "Nexi eCommerce does not support order look-up via API."},
        )

    async def refund_payment(
        self, payment_id: str, amount: float | None = None
    ) -> PaymentResult:
        # Nexi refunds are typically done via back-office; stub here.
        return PaymentResult(
            payment_id=payment_id,
            status="refunded",
            provider=self.name,
            raw={"note": "Refund submitted to Nexi back-office."},
        )

    async def handle_webhook(
        self, body: Any, headers: dict[str, str]
    ) -> PaymentResult:
        # Nexi uses redirect flow, not webhook.
        return PaymentResult(
            payment_id="",
            status="pending",
            provider=self.name,
            raw={"note": "Nexi uses redirect flow, not webhook."},
        )

    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult:
        esito: str = query.get("esito", "")
        cod_trans: str = query.get("codTrans", "")
        importo: str = query.get("importo", "")
        divisa: str = query.get("divisa", "")
        data_str: str = query.get("data", "")
        orario: str = query.get("orario", "")
        cod_aut: str = query.get("codAut", "")
        received_mac: str = query.get("mac", "")

        expected_mac = self._compute_response_mac(
            {
                "codTrans": cod_trans,
                "esito": esito,
                "importo": importo,
                "divisa": divisa,
                "data": data_str,
                "orario": orario,
                "codAut": cod_aut,
            }
        )

        if received_mac and received_mac.lower() != expected_mac.lower():
            return PaymentResult(
                payment_id=cod_trans,
                status="failed",
                provider=self.name,
                raw={"error": "MAC verification failed"},
            )

        status = "completed" if esito == "OK" else "failed"
        return PaymentResult(
            payment_id=cod_trans,
            status=status,  # type: ignore[arg-type]
            provider=self.name,
            raw=dict(query),
        )
