"""Provider abstractions for checkout integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Literal

from .payment import PaymentRequest, PaymentResponse, WebhookPayload

WebhookHandler = Callable[[WebhookPayload], PaymentResponse]


class Provider(ABC):
    """Base provider interface implemented by all payment providers."""

    def __init__(self) -> None:
        self._webhook_handler: WebhookHandler | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider slug (e.g. paypal)."""

    @property
    @abstractmethod
    def flow(self) -> Literal["redirect", "webhook", "direct"]:
        """Payment flow supported by provider."""

    @abstractmethod
    def initiate(self, payment: PaymentRequest) -> PaymentResponse:
        """Initiate a payment request."""

    @abstractmethod
    def verify(
        self, payment_id: str, payload: dict[str, Any] | None = None
    ) -> PaymentResponse:
        """Verify payment status."""

    @abstractmethod
    def refund(self, payment_id: str, amount: float | None = None) -> PaymentResponse:
        """Refund a payment."""

    def register_webhook_handler(self, handler: WebhookHandler) -> None:
        """Register provider-specific webhook handler callback."""
        self._webhook_handler = handler

    def handle_webhook(self, payload: WebhookPayload) -> PaymentResponse:
        """Execute webhook handler if present, otherwise fallback to verify."""
        if self._webhook_handler is not None:
            return self._webhook_handler(payload)
        return self.verify(payload.payment_id, payload.data)
