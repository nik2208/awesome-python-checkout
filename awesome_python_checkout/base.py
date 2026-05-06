"""Abstract base classes for awesome-python-checkout."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from .models import PaymentRequest, PaymentResult, TransactionData


class ITransactionStore(ABC):
    """Interface for persisting transaction data across async callbacks."""

    @abstractmethod
    async def save(self, key: str, data: TransactionData) -> None:
        """Persist *data* under *key*."""

    @abstractmethod
    async def get(self, key: str) -> TransactionData | None:
        """Return the transaction stored under *key*, or ``None``."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the entry stored under *key*."""


class InMemoryTransactionStore(ITransactionStore):
    """Simple in-memory implementation of ITransactionStore for testing."""

    def __init__(self) -> None:
        self._store: dict[str, TransactionData] = {}

    async def save(self, key: str, data: TransactionData) -> None:
        self._store[key] = data

    async def get(self, key: str) -> TransactionData | None:
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class BasePaymentProvider(ABC):
    """Abstract base class that every payment provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique slug identifying this provider (e.g. ``"paypal"``)."""

    @property
    @abstractmethod
    def flow(self) -> Literal["redirect", "webhook", "direct"]:
        """Payment flow type used by this provider."""

    @abstractmethod
    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Initiate a new payment and return the result."""

    @abstractmethod
    async def execute_payment(
        self, payment_id: str, data: dict[str, Any]
    ) -> PaymentResult:
        """Execute / capture an authorised payment."""

    @abstractmethod
    async def get_payment(self, payment_id: str) -> PaymentResult:
        """Retrieve the current state of a payment."""

    @abstractmethod
    async def refund_payment(
        self, payment_id: str, amount: float | None = None
    ) -> PaymentResult:
        """Refund a payment (full or partial)."""

    @abstractmethod
    async def handle_webhook(
        self, body: Any, headers: dict[str, str]
    ) -> PaymentResult:
        """Process an inbound webhook notification from the provider."""

    @abstractmethod
    async def handle_redirect(
        self, query: dict[str, str]
    ) -> PaymentResult:
        """Process the query parameters returned after a provider redirect."""
