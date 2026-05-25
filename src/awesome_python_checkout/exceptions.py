"""Custom exceptions for awesome-python-checkout."""


class CheckoutError(Exception):
    """Base error for checkout operations."""


class ProviderNotRegisteredError(CheckoutError):
    """Raised when a provider is not registered in Checkout."""


class ProviderConfigurationError(CheckoutError):
    """Raised when provider configuration is invalid."""


class PaymentVerificationError(CheckoutError):
    """Raised when payment verification fails."""
