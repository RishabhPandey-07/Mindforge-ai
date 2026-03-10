from datetime import datetime, timezone

from django.conf import settings

from .models import Subscription

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None


PLAN_TO_PRICE_ID = {
    Subscription.PLAN_PRO: "STRIPE_PRICE_ID_PRO",
    Subscription.PLAN_TEAM: "STRIPE_PRICE_ID_TEAM",
}

STRIPE_STATUS_MAP = {
    "trialing": Subscription.STATUS_TRIALING,
    "active": Subscription.STATUS_ACTIVE,
    "past_due": Subscription.STATUS_PAST_DUE,
    "canceled": Subscription.STATUS_CANCELED,
    "unpaid": Subscription.STATUS_PAST_DUE,
}


def stripe_is_configured() -> bool:
    return bool(
        settings.BILLING_MODE == "stripe"
        and stripe
        and settings.STRIPE_SECRET_KEY
        and settings.STRIPE_WEBHOOK_SECRET
    )


def _require_stripe():
    if not stripe:
        raise RuntimeError("stripe package is not installed.")
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    stripe.api_key = settings.STRIPE_SECRET_KEY


def get_price_id_for_plan(plan: str) -> str:
    env_name = PLAN_TO_PRICE_ID.get(plan)
    if not env_name:
        raise RuntimeError("Plan is not billable.")
    price_id = getattr(settings, env_name, "")
    if not price_id:
        raise RuntimeError(f"{env_name} is not configured.")
    return price_id


def create_checkout_session(subscription, success_url: str, cancel_url: str):
    _require_stripe()

    if not subscription.user.email:
        raise RuntimeError("User email is required for checkout.")

    customer_id = subscription.stripe_customer_id or None
    if not customer_id:
        customer = stripe.Customer.create(
            email=subscription.user.email,
            metadata={"user_id": str(subscription.user_id)},
        )
        customer_id = customer["id"]
        subscription.stripe_customer_id = customer_id
        subscription.save(update_fields=["stripe_customer_id", "updated_at"])

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": get_price_id_for_plan(subscription.plan), "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(subscription.user_id), "plan": subscription.plan},
    )
    return session


def build_webhook_event(payload: bytes, signature: str):
    _require_stripe()
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=settings.STRIPE_WEBHOOK_SECRET,
    )


def sync_subscription_from_stripe(stripe_subscription):
    customer_id = stripe_subscription.get("customer")
    if not customer_id:
        return None

    subscription = Subscription.objects.filter(stripe_customer_id=customer_id).select_related("user").first()
    if not subscription:
        return None

    price_id = stripe_subscription["items"]["data"][0]["price"]["id"]
    if price_id == settings.STRIPE_PRICE_ID_PRO:
        subscription.plan = Subscription.PLAN_PRO
    elif price_id == settings.STRIPE_PRICE_ID_TEAM:
        subscription.plan = Subscription.PLAN_TEAM
    else:
        subscription.plan = Subscription.PLAN_FREE

    subscription.stripe_subscription_id = stripe_subscription.get("id", "")
    subscription.status = STRIPE_STATUS_MAP.get(
        stripe_subscription.get("status"),
        Subscription.STATUS_ACTIVE,
    )

    current_period_end = stripe_subscription.get("current_period_end")
    subscription.current_period_end = (
        datetime.fromtimestamp(current_period_end, tz=timezone.utc)
        if current_period_end
        else None
    )
    subscription.save(
        update_fields=[
            "plan",
            "stripe_subscription_id",
            "status",
            "current_period_end",
            "updated_at",
        ]
    )
    return subscription


def cancel_subscription(subscription):
    _require_stripe()
    if subscription.stripe_subscription_id:
        stripe.Subscription.delete(subscription.stripe_subscription_id)

    subscription.plan = Subscription.PLAN_FREE
    subscription.status = Subscription.STATUS_CANCELED
    subscription.current_period_end = None
    subscription.stripe_subscription_id = ""
    subscription.save(
        update_fields=[
            "plan",
            "status",
            "current_period_end",
            "stripe_subscription_id",
            "updated_at",
        ]
    )
    return subscription
