import { expect, it } from "vitest";
import { eventsWithMyParticipation } from "./eventFilters";
import type { CalendarEvent, Member } from "./types";

const members: Member[] = [
  {
    id: 1,
    name: "Anna",
    surname: "One",
    access_level: "member",
    roles: [{ id: 4, name: "Sound", user_ministry_role_id: 10 }],
  },
  {
    id: 2,
    name: "Dima",
    surname: "Two",
    access_level: "member",
    roles: [{ id: 4, name: "Sound", user_ministry_role_id: 20 }],
  },
];
function event(
  id: number,
  roleId: number | null,
  status = "pending",
): CalendarEvent {
  return {
    event_id: id,
    event_name: "Service",
    starts_at: "2026-12-01T10:00:00+04:00",
    additional_info: null,
    rehearsal_at: null,
    event_reminder_at: null,
    rehearsal_reminder_at: null,
    song_ids: [],
    role_slots: [
      {
        id,
        ministry_role_id: 4,
        slot_number: 1,
        user_ministry_role_id: roleId,
        confirmation_status: status,
      },
    ],
  };
}
it("includes both pending and confirmed assignments of the current person", () => {
  const events = [
    event(1, 10),
    event(2, 10, "confirmed"),
    event(3, 20),
    event(4, null),
  ];
  expect(
    eventsWithMyParticipation(events, members, 1).map((item) => item.event_id),
  ).toEqual([1, 2]);
  expect(events).toHaveLength(4);
});
it("does not confuse people with the same ministry role", () => {
  expect(
    eventsWithMyParticipation([event(1, 10), event(2, 20)], members, 2).map(
      (item) => item.event_id,
    ),
  ).toEqual([2]);
});
it("returns no personal assignments when the person has no roles", () => {
  expect(
    eventsWithMyParticipation([event(1, null), event(2, 10)], [], 1),
  ).toEqual([]);
});
