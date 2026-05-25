from __future__ import annotations

import json

import pytest

from awesome_python_checkout import DjangoAdapter, FastAPIAdapter, FlaskAdapter


class DjangoRequest:
    def __init__(self, payload: dict[str, object]) -> None:
        self.body = json.dumps(payload).encode("utf-8")


class FlaskRequest:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def get_json(self, silent: bool = True) -> dict[str, object]:
        return self._payload


class FastAPIRequest:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    async def json(self) -> dict[str, object]:
        return self._payload


def test_django_adapter_parse_payment() -> None:
    req = DjangoRequest({"amount": 19.9, "order_id": "ord-1"})
    model = DjangoAdapter.parse_payment_request(req)
    assert model.amount == 19.9


def test_flask_adapter_parse_payment() -> None:
    req = FlaskRequest({"amount": 30, "order_id": "ord-2"})
    model = FlaskAdapter.parse_payment_request(req)
    assert model.order_id == "ord-2"


@pytest.mark.asyncio
async def test_fastapi_adapter_parse_webhook() -> None:
    req = FastAPIRequest(
        {"event": "payment.completed", "id": "p-1", "status": "completed"}
    )
    payload = await FastAPIAdapter.parse_webhook_payload(req, "paypal")
    assert payload.provider == "paypal"
