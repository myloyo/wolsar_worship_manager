from fastapi import APIRouter

from worship_bot.api.routers import (
    accounts,
    churches,
    credentials,
    event_lifecycle,
    event_preferences,
    event_templates,
    events,
    membership_requests,
    ministries,
    my_events,
    notifications,
    participants,
    planning,
    portal,
    registration,
    web_push,
)

router = APIRouter(prefix="/api/v1")
router.include_router(churches.router)
router.include_router(participants.router)
router.include_router(events.router)
router.include_router(ministries.router)
router.include_router(registration.router)
router.include_router(event_lifecycle.router)
router.include_router(event_preferences.router)
router.include_router(portal.router)
router.include_router(portal.internal_router)
router.include_router(planning.router)
router.include_router(notifications.router)

router.include_router(web_push.router)

router.include_router(event_templates.router)

router.include_router(credentials.router)

router.include_router(membership_requests.router)

router.include_router(accounts.router)
router.include_router(accounts.internal_router)

router.include_router(membership_requests.internal_router)

router.include_router(my_events.router)
router.include_router(my_events.internal_router)
