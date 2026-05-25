"""Payment and webhook models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PaymentRequest(BaseModel):
    """Input model used to initiate a payment."""

    amount: float = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    description: str = ""
    order_id: str
    return_url: str = ""
    cancel_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentResponse(BaseModel):
    """Standardized response returned by providers."""

    payment_id: str
    provider: str
    status: Literal["pending", "completed", "failed", "refunded"]
    flow: Literal["redirect", "webhook", "direct"]
    redirect_url: str | None = None
    amount: float | None = None
    currency: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class WebhookPayload(BaseModel):
    """Normalized webhook payload."""

    event: str
    payment_id: str
    provider: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
