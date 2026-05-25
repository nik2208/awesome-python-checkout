"""Django adapter helpers."""

from __future__ import annotations

import json
from typing import Any

from ..core.payment import PaymentRequest, WebhookPayload


class DjangoAdapter:
    """Request/response adapter for Django integration."""

    @staticmethod
    def parse_payment_request(request: Any) -> PaymentRequest:
        body = (
            json.loads(request.body.decode("utf-8"))
            if getattr(request, "body", b"")
            else {}
        )
        return PaymentRequest.model_validate(body)

    @staticmethod
    def parse_webhook_payload(request: Any, provider: str) -> WebhookPayload:
        body = (
            json.loads(request.body.decode("utf-8"))
            if getattr(request, "body", b"")
            else {}
        )
        return WebhookPayload(
            event=body.get("event", "unknown"),
            payment_id=body.get("id", ""),
            provider=provider,
            status=body.get("status", "pending"),
            data=body,
        )

    @staticmethod
    def json_response(data: dict[str, Any], status: int = 200) -> Any:
        try:
            from django.http import JsonResponse  # type: ignore[import-not-found]

            return JsonResponse(data, status=status)
        except Exception:
            return {"status": status, "data": data}
