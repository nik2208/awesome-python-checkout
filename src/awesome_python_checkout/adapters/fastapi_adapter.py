"""FastAPI adapter helpers."""

from __future__ import annotations

from typing import Any

from ..core.payment import PaymentRequest, WebhookPayload


class FastAPIAdapter:
    """Request/response adapter for FastAPI integration."""

    @staticmethod
    async def parse_payment_request(request: Any) -> PaymentRequest:
        body = await request.json()
        return PaymentRequest.model_validate(body)

    @staticmethod
    async def parse_webhook_payload(request: Any, provider: str) -> WebhookPayload:
        body = await request.json()
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
            from fastapi.responses import JSONResponse

            return JSONResponse(content=data, status_code=status)
        except Exception:
            return {"status": status, "data": data}
