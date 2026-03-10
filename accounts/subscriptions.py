from .models import Subscription


PLAN_FEATURES = {
    Subscription.PLAN_FREE: {
        "journal",
        "basic_insights",
        "mood_trends",
    },
    Subscription.PLAN_PRO: {
        "journal",
        "basic_insights",
        "mood_trends",
        "ai_summary",
        "mind_chat",
        "weekly_review",
    },
    Subscription.PLAN_TEAM: {
        "journal",
        "basic_insights",
        "mood_trends",
        "ai_summary",
        "mind_chat",
        "weekly_review",
        "team_workspace",
    },
}


def get_or_create_subscription(user):
    subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": Subscription.PLAN_FREE,
            "status": Subscription.STATUS_ACTIVE,
        },
    )
    return subscription


def has_feature(user, feature_name: str) -> bool:
    if not user.is_authenticated:
        return False
    subscription = get_or_create_subscription(user)
    return feature_name in PLAN_FEATURES.get(subscription.plan, set())
