# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-06

### Added

- Initial release of `awesome-python-checkout`.
- Python / FastAPI port of [awesome-node-checkout](https://github.com/nik2208/awesome-node-checkout).
- `CheckoutConfigurator` with `register_provider()` (chainable), `create_payment()`, `execute_payment()`, `get_payment()`, `refund_payment()`, `handle_webhook()`, `handle_redirect()`, and `router()`.
- `BasePaymentProvider` abstract base class with the full six-method interface.
- `ITransactionStore` abstract base class with `save()`, `get()`, `delete()`.
- `InMemoryTransactionStore` for testing and prototyping.
- `PaymentRequest`, `PaymentResult`, and `TransactionData` Pydantic v2 models.
- FastAPI `APIRouter` (via `checkout.router()`) exposing the six standard checkout routes.
- Event system: `checkout.on(event, callback)` and `await checkout.emit(event, payload)` for the five standard events (`payment.created`, `payment.completed`, `payment.failed`, `payment.refunded`, `webhook.received`).
- `PayPalProvider` — PayPal Orders API v2, redirect flow.
- `NexiProvider` — Nexi eCommerce DispatcherServlet, redirect flow, MAC SHA-1 signature.
- `SatispayProvider` — Satispay Business API v1, webhook flow, RSA-SHA256 request signing.
- GitHub Actions CI (Python 3.11 & 3.12) and PyPI publish via OIDC Trusted Publishing.
- Full GitHub community compliance: `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, issue templates, PR template.
