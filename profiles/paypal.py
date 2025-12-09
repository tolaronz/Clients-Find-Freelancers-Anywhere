import requests
from dataclasses import dataclass
from typing import Dict, Tuple

from django.conf import settings


@dataclass(frozen=True)
class TierPrice:
    amount: str  # string to avoid float issues; PayPal expects stringified decimal
    currency: str = "USD"


TIER_PRICING: Dict[str, TierPrice] = {
    "plus": TierPrice("29.00"),
    "pro": TierPrice("59.00"),
}


class PayPalError(Exception):
    pass


def _base_url() -> str:
    env = (settings.PAYPAL_ENV or "sandbox").lower()
    return "https://api-m.paypal.com" if env == "live" else "https://api-m.sandbox.paypal.com"


def _get_access_token() -> str:
    if settings.PAYPAL_BYPASS:
        return "BYPASS"

    client_id = settings.PAYPAL_CLIENT_ID
    secret = settings.PAYPAL_CLIENT_SECRET
    if not client_id or not secret:
        raise PayPalError("PayPal credentials missing")

    resp = requests.post(
        f"{_base_url()}/v1/oauth2/token",
        auth=(client_id, secret),
        headers={"Accept": "application/json"},
        data={"grant_type": "client_credentials"},
        timeout=6,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise PayPalError("No access token returned from PayPal")
    return token


def _price_for_tier(tier: str) -> TierPrice:
    tier = (tier or "").lower()
    return TIER_PRICING.get(tier, TierPrice("0.00"))


def verify_payment(order_id: str, tier: str) -> bool:
    """
    Verify a PayPal order/capture before upgrading a plan.
    - For local/dev, set PAYPAL_BYPASS=true to skip verification.
    """
    if not order_id:
        return False

    if settings.PAYPAL_BYPASS or settings.REVENUECAT_BYPASS:
        return True

    try:
        token = _get_access_token()
    except Exception:
        return False

    expected = _price_for_tier(tier)

    try:
        resp = requests.get(
            f"{_base_url()}/v2/checkout/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return False

    status = data.get("status")
    purchase_units = data.get("purchase_units", [])
    amount_info: Tuple[str, str] = ("", "")
    if purchase_units:
        amt = purchase_units[0].get("amount", {})
        amount_info = (amt.get("value", ""), amt.get("currency_code", ""))

    correct_amount = amount_info[0] == expected.amount and amount_info[1].upper() == expected.currency
    return status == "COMPLETED" and correct_amount
