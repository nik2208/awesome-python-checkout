"""FastAPI router exposing the six checkout endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .models import PaymentRequest, PaymentResult

if TYPE_CHECKING:
    from .configurator import CheckoutConfigurator


def build_router(checkout: "CheckoutConfigurator") -> APIRouter:
    """Build and return the six-route checkout ``APIRouter``.

    Routes
    ------
    POST   /{provider}            Create a payment
    POST   /{provider}/execute    Execute / capture a payment
    GET    /{provider}/redirect   Handle provider redirect callback
    GET    /{provider}/{id}       Get payment details
    POST   /{provider}/refund     Refund a payment
    POST   /{provider}/webhook    Handle provider webhook
    """
    router = APIRouter()

    @router.post("/{provider}", response_model=PaymentResult)
    async def create_payment(
        provider: str, request_body: PaymentRequest
    ) -> PaymentResult:
        try:
            return await checkout.create_payment(provider, request_body)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/{provider}/execute", response_model=PaymentResult)
    async def execute_payment(
        provider: str, request: Request
    ) -> PaymentResult:
        try:
            body: dict[str, Any] = await request.json()
        except Exception:
            body = {}
        payment_id: str = body.get("payment_id", "")
        data: dict[str, Any] = body.get("data", {})
        try:
            return await checkout.execute_payment(provider, payment_id, data)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.get("/{provider}/redirect", response_model=PaymentResult)
    async def handle_redirect(
        provider: str, request: Request
    ) -> PaymentResult:
        query: dict[str, str] = dict(request.query_params)
        try:
            return await checkout.handle_redirect(provider, query)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.get("/{provider}/{payment_id}", response_model=PaymentResult)
    async def get_payment(provider: str, payment_id: str) -> PaymentResult:
        try:
            return await checkout.get_payment(provider, payment_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/{provider}/refund", response_model=PaymentResult)
    async def refund_payment(
        provider: str, request: Request
    ) -> PaymentResult:
        try:
            body = await request.json()
        except Exception:
            body = {}
        payment_id: str = body.get("payment_id", "")
        amount: float | None = body.get("amount")
        try:
            return await checkout.refund_payment(provider, payment_id, amount)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/{provider}/webhook")
    async def handle_webhook(provider: str, request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = await request.body()
        headers: dict[str, str] = dict(request.headers)
        try:
            result = await checkout.handle_webhook(provider, body, headers)
            return JSONResponse(content=result.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return router
