"""Main Checkout orchestration class."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from ..exceptions import ProviderNotRegisteredError
from .payment import PaymentRequest, PaymentResponse, WebhookPayload
from .provider import Provider

EventCallback = Callable[[dict[str, Any]], None]


class Checkout:
    """Framework-agnostic checkout manager with provider registry and events."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._listeners: dict[str, list[EventCallback]] = defaultdict(list)

    def register_provider(self, provider: Provider) -> "Checkout":
        """Register provider and return self."""
        self._providers[provider.name] = provider
        return self

    def get_provider(self, name: str) -> Provider:
        """Get registered provider by name."""
        provider = self._providers.get(name)
        if provider is None:
            raise ProviderNotRegisteredError(f"Provider '{name}' is not registered")
        return provider

    def on(self, event: str, callback: EventCallback) -> "Checkout":
        """Subscribe callback to checkout lifecycle event."""
        self._listeners[event].append(callback)
        return self

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        """Emit lifecycle event."""
        for callback in self._listeners.get(event, []):
            callback(payload)

    def create_payment(
        self, provider_name: str, payment: PaymentRequest
    ) -> PaymentResponse:
        """Create payment through provider."""
        provider = self.get_provider(provider_name)
        result = provider.initiate(payment)
        self.emit(
            "payment.created",
            {
                "provider": provider_name,
                "payment_id": result.payment_id,
                "status": result.status,
            },
        )
        return result

    def verify_payment(
        self,
        provider_name: str,
        payment_id: str,
        payload: dict[str, Any] | None = None,
    ) -> PaymentResponse:
        """Verify payment and emit status events."""
        provider = self.get_provider(provider_name)
        result = provider.verify(payment_id, payload)
        self._emit_payment_status(provider_name, result)
        return result

    def refund_payment(
        self, provider_name: str, payment_id: str, amount: float | None = None
    ) -> PaymentResponse:
        """Refund payment through provider."""
        provider = self.get_provider(provider_name)
        result = provider.refund(payment_id, amount)
        self.emit(
            "payment.refunded",
            {"provider": provider_name, "payment_id": result.payment_id},
        )
        return result

    def handle_webhook(
        self, provider_name: str, payload: WebhookPayload
    ) -> PaymentResponse:
        """Dispatch incoming webhook payload to provider handler."""
        provider = self.get_provider(provider_name)
        result = provider.handle_webhook(payload)
        self.emit(
            "webhook.received",
            {
                "provider": provider_name,
                "payment_id": payload.payment_id,
                "event": payload.event,
            },
        )
        self._emit_payment_status(provider_name, result)
        return result

    def _emit_payment_status(
        self, provider_name: str, response: PaymentResponse
    ) -> None:
        if response.status == "completed":
            self.emit(
                "payment.completed",
                {"provider": provider_name, "payment_id": response.payment_id},
            )
        elif response.status == "failed":
            self.emit(
                "payment.failed",
                {
                    "provider": provider_name,
                    "payment_id": response.payment_id,
                    "raw": response.raw,
                },
            )
