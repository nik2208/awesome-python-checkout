"""Pydantic models for awesome-python-checkout."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class PaymentRequest(BaseModel):
    """Request model for creating a payment."""

    amount: float
    currency: str = "EUR"
    description: str = ""
    return_url: str = ""
    cancel_url: str = ""
    order_id: str = ""
    metadata: dict[str, Any] = {}


class PaymentResult(BaseModel):
    """Result model returned by payment operations."""

    payment_id: str
    status: Literal["pending", "completed", "failed", "refunded"]
    provider: str
    amount: float | None = None
    currency: str | None = None
    redirect_url: str | None = None
    raw: dict[str, Any] = {}


class TransactionData(BaseModel):
    """Data persisted in ITransactionStore to correlate async callbacks."""

    payment_id: str
    order_id: str
    amount: float
    currency: str
    provider: str
    metadata: dict[str, Any] = {}
