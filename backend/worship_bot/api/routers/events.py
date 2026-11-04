from fastapi import APIRouter, Depends, status

from worship_bot.api.handlers import events
from worship_bot.api.schemas import (
    AssignmentRead,
    EventCalendarItemRead,
    EventRead,
    EventRoleSlotRead,
    EventTypeRead,
)
from worship_bot.api.security import require_bot_service

router = APIRouter(dependencies=[Depends(require_bot_service)], tags=["events"])
router.add_api_route(
    "/event-types", events.list_event_types, methods=["GET"], response_model=list[EventTypeRead]
)
router.add_api_route(
    "/events",
    events.create_event,
    methods=["POST"],
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route("/events", events.list_events, methods=["GET"], response_model=list[EventRead])
router.add_api_route(
    "/events/{event_id}/participants",
    events.assign_participant,
    methods=["POST"],
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/ministries/{church_ministry_id}/event-series",
    events.create_event_series,
    methods=["POST"],
    response_model=list[EventCalendarItemRead],
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/calendar/events",
    events.list_calendar_events,
    methods=["GET"],
    response_model=list[EventCalendarItemRead],
)
router.add_api_route(
    "/events/{event_id}/role-slots",
    events.add_event_role_slot,
    methods=["POST"],
    response_model=EventRoleSlotRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/event-role-slots/{slot_id}/assignment",
    events.assign_event_role_slot,
    methods=["PUT"],
    response_model=EventRoleSlotRead,
)
