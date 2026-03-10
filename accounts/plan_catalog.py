from .models import Subscription


PLAN_CATALOG = [
    {
        "code": Subscription.PLAN_FREE,
        "name": "Free",
        "price": "$0",
        "features": [
            "Daily journaling",
            "Basic insights",
            "Mood trends",
        ],
    },
    {
        "code": Subscription.PLAN_PRO,
        "name": "Pro",
        "price": "$15/mo",
        "features": [
            "AI summaries",
            "Mind chat",
            "Weekly AI reviews",
            "Priority analytics features",
        ],
    },
    {
        "code": Subscription.PLAN_TEAM,
        "name": "Team",
        "price": "$49/mo",
        "features": [
            "Everything in Pro",
            "Shared team workspace foundation",
            "Usage analytics",
            "Future admin controls",
        ],
    },
]
