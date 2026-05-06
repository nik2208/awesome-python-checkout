"""CheckoutConfigurator — the central orchestration class."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from fastapi import APIRouter

from .base import BasePaymentProvider
from .models import PaymentRequest, PaymentResult


class CheckoutConfigurator:
    """Orchestrates multiple payment providers with a unified API.

    Usage::

        checkout = CheckoutConfigurator()
        checkout.register_provider(PayPalProvider(...))
        checkout.register_provider(NexiProvider(...))

        result = await checkout.create_payment("paypal", PaymentRequest(...))

    Providers are registered by name; the configurator dispatches every call to
    the matching provider and fires the appropriate lifecycle event.
    """

    def __init__(self) -> None:
        self._providers: dict[str, BasePaymentProvider] = {}
        self._listeners: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Provider registration
    # ------------------------------------------------------------------

    def register_provider(self, provider: BasePaymentProvider) -> "CheckoutConfigurator":
        """Register *provider* and return ``self`` for chaining."""
        self._providers[provider.name] = provider
        return self

    def _get_provider(self, name: str) -> BasePaymentProvider:
        if name not in self._providers:
            raise ValueError(f"Provider '{name}' is not registered.")
        return self._providers[name]

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def on(self, event: str, callback: Callable[..., Any]) -> "CheckoutConfigurator":
        """Subscribe *callback* to *event*.  Returns ``self`` for chaining."""
        self._listeners[event].append(callback)
        return self

    async def emit(self, event: str, payload: Any) -> None:
        """Fire all callbacks registered for *event*."""
        for cb in self._listeners.get(event, []):
            result = cb(payload)
            if hasattr(result, "__await__"):
                await result

    # ------------------------------------------------------------------
    # Payment operations
    # ------------------------------------------------------------------

    async def create_payment(
        self, provider_name: str, request: PaymentRequest
    ) -> PaymentResult:
        """Create a payment via *provider_name*."""
        provider = self._get_provider(provider_name)
        result = await provider.create_payment(request)
        await self.emit(
            "payment.created",
            {"provider": provider_name, "paymentId": result.payment_id},
        )
        return result

    async def execute_payment(
        self, provider_name: str, payment_id: str, data: dict[str, Any]
    ) -> PaymentResult:
        """Execute / capture a payment via *provider_name*."""
        provider = self._get_provider(provider_name)
        result = await provider.execute_payment(payment_id, data)
        if result.status == "completed":
            await self.emit(
                "payment.completed",
                {"provider": provider_name, "paymentId": result.payment_id},
            )
        elif result.status == "failed":
            await self.emit(
                "payment.failed",
                {"provider": provider_name, "error": result.raw},
            )
        return result

    async def get_payment(
        self, provider_name: str, payment_id: str
    ) -> PaymentResult:
        """Get the state of an existing payment."""
        provider = self._get_provider(provider_name)
        return await provider.get_payment(payment_id)

    async def refund_payment(
        self, provider_name: str, payment_id: str, amount: float | None = None
    ) -> PaymentResult:
        """Refund a payment via *provider_name*."""
        provider = self._get_provider(provider_name)
        result = await provider.refund_payment(payment_id, amount)
        await self.emit(
            "payment.refunded",
            {"provider": provider_name, "paymentId": result.payment_id},
        )
        return result

    async def handle_webhook(
        self, provider_name: str, body: Any, headers: dict[str, str]
    ) -> PaymentResult:
        """Deliver a raw webhook payload to *provider_name*."""
        provider = self._get_provider(provider_name)
        result = await provider.handle_webhook(body, headers)
        await self.emit(
            "webhook.received",
            {"provider": provider_name, "data": body},
        )
        if result.status == "completed":
            await self.emit(
                "payment.completed",
                {"provider": provider_name, "paymentId": result.payment_id},
            )
        elif result.status == "failed":
            await self.emit(
                "payment.failed",
                {"provider": provider_name, "error": result.raw},
            )
        return result

    async def handle_redirect(
        self, provider_name: str, query: dict[str, str]
    ) -> PaymentResult:
        """Process query parameters returned by a provider redirect."""
        provider = self._get_provider(provider_name)
        result = await provider.handle_redirect(query)
        if result.status == "completed":
            await self.emit(
                "payment.completed",
                {"provider": provider_name, "paymentId": result.payment_id},
            )
        elif result.status == "failed":
            await self.emit(
                "payment.failed",
                {"provider": provider_name, "error": result.raw},
            )
        return result

    # ------------------------------------------------------------------
    # FastAPI router
    # ------------------------------------------------------------------

    def router(self) -> APIRouter:
        """Return a FastAPI ``APIRouter`` with the six checkout routes.

        Mount it with::

            app.include_router(checkout.router(), prefix="/checkout")
        """
        from .router import build_router  # avoid circular import at module level

        return build_router(self)
