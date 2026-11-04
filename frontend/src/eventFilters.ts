import type { CalendarEvent, Member } from "./types";

export function eventsWithMyParticipation(
  events: CalendarEvent[],
  members: Member[],
  userId: number,
): CalendarEvent[] {
  const ownRoles = new Set(
    members
      .find((member) => member.id === userId)
      ?.roles.map((role) => role.user_ministry_role_id) || [],
  );
  return events.filter((event) =>
    event.role_slots.some(
      (slot) =>
        slot.user_ministry_role_id !== null &&
        ownRoles.has(slot.user_ministry_role_id),
    ),
  );
}
