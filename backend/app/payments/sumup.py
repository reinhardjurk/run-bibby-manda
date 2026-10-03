"""SumUp Hosted Checkout client. Credentials are per organization; status is only ever
verified server-side (GET checkout), never trusted from a redirect or webhook payload."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

log = logging.getLogger("bibby.payments")


class PaymentProviderError(Exception):
    pass


@dataclass
class CheckoutResult:
    checkout_id: str
    hosted_url: str


@dataclass
class CheckoutStatus:
    status: str  # PENDING | PAID | FAILED | EXPIRED
    transaction_code: str | None = None


class SumUpClient:
    def __init__(self, api_key: str, merchant_code: str) -> None:
        self.api_key = api_key
        self.merchant_code = merchant_code
        self.base = get_settings().sumup_api_base

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def create_checkout(
        self, amount_cents: int, reference: str, description: str, redirect_url: str
    ) -> CheckoutResult:
        payload = {
            "checkout_reference": reference,
            "amount": round(amount_cents / 100, 2),
            "currency": "EUR",
            "merchant_code": self.merchant_code,
            "description": description,
            "hosted_checkout": {"enabled": True},
            "redirect_url": redirect_url,
            "return_url": redirect_url,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{self.base}/v0.1/checkouts", json=payload, headers=self._headers()
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.error("sumup create_checkout failed: %s", exc)
            raise PaymentProviderError("Zahlungsanbieter nicht erreichbar.") from exc
        hosted = data.get("hosted_checkout_url") or data.get("hosted_checkout", {}).get("url")
        if not data.get("id") or not hosted:
            raise PaymentProviderError("Zahlungsanbieter lieferte keine Bezahlseite.")
        return CheckoutResult(checkout_id=str(data["id"]), hosted_url=str(hosted))

    async def get_checkout(self, checkout_id: str) -> CheckoutStatus:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{self.base}/v0.1/checkouts/{checkout_id}", headers=self._headers()
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.error("sumup get_checkout failed: %s", exc)
            raise PaymentProviderError("Zahlungsanbieter nicht erreichbar.") from exc
        code = None
        for tx in data.get("transactions") or []:
            if tx.get("status") == "SUCCESSFUL":
                code = tx.get("transaction_code")
        return CheckoutStatus(status=str(data.get("status", "PENDING")), transaction_code=code)


class FakeSumUpClient(SumUpClient):
    """Deterministic in-memory provider for tests and load tests (no network)."""

    checkouts: dict[str, CheckoutStatus] = {}
    fail_create: bool = False
    counter: int = 0

    async def create_checkout(
        self, amount_cents: int, reference: str, description: str, redirect_url: str
    ) -> CheckoutResult:
        if FakeSumUpClient.fail_create:
            raise PaymentProviderError("Zahlungsanbieter nicht erreichbar.")
        FakeSumUpClient.counter += 1
        cid = f"fake-checkout-{FakeSumUpClient.counter}"
        FakeSumUpClient.checkouts[cid] = CheckoutStatus(status="PENDING")
        return CheckoutResult(checkout_id=cid, hosted_url=f"https://pay.example.org/{cid}")

    async def get_checkout(self, checkout_id: str) -> CheckoutStatus:
        return FakeSumUpClient.checkouts.get(checkout_id, CheckoutStatus(status="FAILED"))

    @classmethod
    def mark_paid(cls, checkout_id: str, code: str = "TXCODE123") -> None:
        cls.checkouts[checkout_id] = CheckoutStatus(status="PAID", transaction_code=code)


def make_client(api_key: str, merchant_code: str) -> SumUpClient:
    if get_settings().payment_provider == "fake":
        return FakeSumUpClient(api_key, merchant_code)
    return SumUpClient(api_key, merchant_code)
