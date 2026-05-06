# awesome-python-checkout

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/awesome-python-checkout.svg)](https://pypi.org/project/awesome-python-checkout/)

**FastAPI payment checkout library** — a faithful Python port of [awesome-node-checkout](https://github.com/nik2208/awesome-node-checkout).

Drop-in payment orchestration for FastAPI — connect any payment provider through a single interface.  
Inspired by [awesome-python-auth](https://github.com/nik2208/awesome-python-auth). Same philosophy: no framework lock-in, no DB lock-in, implement one interface and you're done.

---

## Installation

```bash
pip install awesome-python-checkout
```

---

## Quick Start

### Standalone (no HTTP framework)

```python
import asyncio
from awesome_python_checkout import CheckoutConfigurator, PayPalProvider, PayPalConfig, PaymentRequest

checkout = CheckoutConfigurator()
checkout.register_provider(
    PayPalProvider(PayPalConfig(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        environment="sandbox",
    ))
)

async def main():
    result = await checkout.create_payment(
        "paypal",
        PaymentRequest(
            amount=49.99,
            currency="EUR",
            description="Order #1234",
            return_url="https://myapp.com/payment/success",
            cancel_url="https://myapp.com/payment/cancel",
            order_id="ORD-1234",
        ),
    )
    print(result.redirect_url)  # redirect user to this URL

asyncio.run(main())
```

### FastAPI router mounting

```python
import os
from fastapi import FastAPI
from awesome_python_checkout import (
    CheckoutConfigurator,
    PayPalProvider, PayPalConfig,
    NexiProvider, NexiConfig,
    SatispayProvider, SatispayConfig,
)

checkout = CheckoutConfigurator()

checkout \
    .register_provider(PayPalProvider(PayPalConfig(
        client_id=os.environ["PAYPAL_CLIENT_ID"],
        client_secret=os.environ["PAYPAL_CLIENT_SECRET"],
        environment="sandbox",
    ))) \
    .register_provider(NexiProvider(NexiConfig(
        merchant_id=os.environ["NEXI_MERCHANT_ID"],
        mac_key=os.environ["NEXI_MAC_KEY"],
        environment="sandbox",
    ))) \
    .register_provider(SatispayProvider(SatispayConfig(
        key_id=os.environ["SATISPAY_KEY_ID"],
        private_key=open("private.pem").read(),
        environment="sandbox",
        server_url="https://myapp.com",
    )))

app = FastAPI()
app.include_router(checkout.router(), prefix="/checkout")
```

---

## CheckoutConfig Reference

### PayPalConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `client_id` | `str` | required | PayPal OAuth2 client ID |
| `client_secret` | `str` | required | PayPal OAuth2 client secret |
| `environment` | `"sandbox" \| "live"` | `"sandbox"` | Target environment |

### NexiConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `merchant_id` | `str` | required | Nexi merchant alias |
| `mac_key` | `str` | required | Nexi MAC key for SHA-1 signature |
| `environment` | `"sandbox" \| "live"` | `"sandbox"` | Target environment |

### SatispayConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key_id` | `str` | required | Satispay RSA key ID |
| `private_key` | `str` | required | RSA private key (PEM string) |
| `environment` | `"sandbox" \| "live"` | `"sandbox"` | Target environment |
| `server_url` | `str` | `""` | Public base URL of your server (used to build the webhook callback URL) |
| `store` | `ITransactionStore` | `InMemoryTransactionStore()` | Transaction store for correlating webhooks |

---

## Routes

All routes are mounted under the prefix you choose (e.g. `/checkout`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/{provider}` | Create a payment |
| `POST` | `/{provider}/execute` | Execute / capture a payment |
| `GET`  | `/{provider}/redirect` | Handle provider redirect callback |
| `GET`  | `/{provider}/{id}` | Get payment details |
| `POST` | `/{provider}/refund` | Refund a payment |
| `POST` | `/{provider}/webhook` | Handle provider webhook |

---

## Payment Flows

| Flow | Providers | Description |
|------|-----------|-------------|
| `redirect` | PayPal, Nexi | User is redirected to the provider page, then returns with query params |
| `webhook` | Satispay | Provider calls the webhook URL asynchronously after confirmation |
| `direct` | *(future)* | Synchronous processing (card tokenisation, etc.) |

---

## Events

Subscribe to lifecycle events with `checkout.on()`:

```python
checkout \
    .on("payment.created",   lambda p: print("created",   p["paymentId"])) \
    .on("payment.completed", lambda p: print("completed", p["paymentId"])) \
    .on("payment.failed",    lambda p: print("failed",    p["error"])) \
    .on("payment.refunded",  lambda p: print("refunded",  p["paymentId"])) \
    .on("webhook.received",  lambda p: print("webhook",   p["data"]))
```

Async callbacks are also supported:

```python
async def on_completed(payload):
    await notify_order_service(payload["paymentId"])

checkout.on("payment.completed", on_completed)
```

| Event | Payload keys | Fired when |
|-------|-------------|------------|
| `payment.created` | `provider`, `paymentId` | `create_payment` succeeds |
| `payment.completed` | `provider`, `paymentId` | execute / redirect / webhook confirms success |
| `payment.failed` | `provider`, `error` | payment fails |
| `payment.refunded` | `provider`, `paymentId` | refund succeeds |
| `webhook.received` | `provider`, `data` | webhook body arrives |

---

## Custom Transaction Store

Implement `ITransactionStore` to persist transactions in your database:

```python
from awesome_python_checkout import ITransactionStore, TransactionData

class RedisTransactionStore(ITransactionStore):
    async def save(self, key: str, data: TransactionData) -> None:
        await redis.set(key, data.model_dump_json(), ex=3600)

    async def get(self, key: str) -> TransactionData | None:
        raw = await redis.get(key)
        return TransactionData.model_validate_json(raw) if raw else None

    async def delete(self, key: str) -> None:
        await redis.delete(key)
```

Pass the store to the provider config:

```python
from awesome_python_checkout import SatispayProvider, SatispayConfig

provider = SatispayProvider(SatispayConfig(
    key_id="...",
    private_key="...",
    store=RedisTransactionStore(),
))
```

---

## Custom Provider

Extend `BasePaymentProvider` to add your own payment gateway:

```python
from awesome_python_checkout import BasePaymentProvider, PaymentRequest, PaymentResult
from typing import Any, Literal

class StripeProvider(BasePaymentProvider):
    @property
    def name(self) -> str:
        return "stripe"

    @property
    def flow(self) -> Literal["redirect"]:
        return "redirect"

    async def create_payment(self, request: PaymentRequest) -> PaymentResult:
        # call Stripe API …
        return PaymentResult(
            payment_id="pi_xxx",
            status="pending",
            provider=self.name,
            redirect_url="https://checkout.stripe.com/pay/…",
        )

    async def execute_payment(self, payment_id: str, data: dict[str, Any]) -> PaymentResult: ...
    async def get_payment(self, payment_id: str) -> PaymentResult: ...
    async def refund_payment(self, payment_id: str, amount: float | None = None) -> PaymentResult: ...
    async def handle_webhook(self, body: Any, headers: dict[str, str]) -> PaymentResult: ...
    async def handle_redirect(self, query: dict[str, str]) -> PaymentResult: ...

checkout.register_provider(StripeProvider())
```

---

## Built-in Providers

| Provider | Flow | Notes |
|----------|------|-------|
| `PayPalProvider` | redirect | PayPal Orders API v2 |
| `NexiProvider` | redirect | Nexi eCommerce DispatcherServlet, MAC SHA-1 |
| `SatispayProvider` | webhook | Satispay Business API v1, RSA-SHA256 signing |

---

## Angular Integration

Point your Angular app (using [ng-awesome-node-auth](https://github.com/nik2208/ng-awesome-node-auth) or any HTTP client) at the FastAPI server:

```typescript
// Call the checkout API directly from Angular
const result = await http.post('/checkout/paypal', {
  amount: 49.99,
  currency: 'EUR',
  order_id: 'ORD-1234',
  return_url: 'https://myapp.com/success',
  cancel_url: 'https://myapp.com/cancel',
}).toPromise();

window.location.href = result.redirect_url;
```

No other changes needed — the FastAPI server handles all provider communication.

---

## Flutter Integration

Call the checkout endpoints from your Flutter app:

```dart
final response = await http.post(
  Uri.parse('https://your-server.com/checkout/paypal'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'amount': 49.99,
    'currency': 'EUR',
    'order_id': 'ORD-1234',
    'return_url': 'https://your-server.com/success',
    'cancel_url': 'https://your-server.com/cancel',
  }),
);
final data = jsonDecode(response.body);
// Open data['redirect_url'] in a WebView or browser
```

---

## License

MIT