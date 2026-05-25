"""Flask adapter helpers."""

from __future__ import annotations

from typing import Any

from ..core.payment import PaymentRequest, WebhookPayload


class FlaskAdapter:
    """Request/response adapter for Flask integration."""

    @staticmethod
    def parse_payment_request(request: Any) -> PaymentRequest:
        body = request.get_json(silent=True) or {}
        return PaymentRequest.model_validate(body)

    @staticmethod
    def parse_webhook_payload(request: Any, provider: str) -> WebhookPayload:
        body = request.get_json(silent=True) or {}
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
            from flask import jsonify  # type: ignore[import-not-found]

            response = jsonify(data)
            response.status_code = status
            return response
        except Exception:
            return {"status": status, "data": data}
