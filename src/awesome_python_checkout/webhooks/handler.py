"""Generic webhook handler."""

from __future__ import annotations

from ..core.checkout import Checkout
from ..core.payment import PaymentResponse, WebhookPayload


class WebhookHandler:
    """Coordinates webhook processing through Checkout."""

    def __init__(self, checkout: Checkout) -> None:
        self.checkout = checkout

    def process(self, provider_name: str, payload: WebhookPayload) -> PaymentResponse:
        """Process webhook payload for a specific provider."""
        return self.checkout.handle_webhook(provider_name, payload)
