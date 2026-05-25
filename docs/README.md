# awesome-python-checkout

A production-ready Python port of `awesome-node-checkout` with provider abstractions, adapters, and webhook handling.

## Features

- Framework-agnostic core (`Checkout` + `Provider`)
- Built-in providers: PayPal, Nexi, Satispay
- Payment flows: redirect, webhook, direct
- Adapters for Django, FastAPI, Flask
- Typed models with Pydantic

## Installation

```bash
pip install awesome-python-checkout
```

## Quick Start

```python
from awesome_python_checkout import Checkout, PayPalProvider, PayPalConfig, PaymentRequest

checkout = Checkout()
checkout.register_provider(PayPalProvider(PayPalConfig(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    environment="sandbox",
)))

response = checkout.create_payment(
    "paypal",
    PaymentRequest(
        amount=49.99,
        currency="EUR",
        order_id="ORD-1234",
        description="Order #1234",
        return_url="https://myapp.com/success",
        cancel_url="https://myapp.com/cancel",
    ),
)

print(response.redirect_url)
```

## Framework Adapters

- `DjangoAdapter`
- `FastAPIAdapter`
- `FlaskAdapter`

## Testing

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v --tb=short
```

## Contributing

See `CONTRIBUTING.md`.
