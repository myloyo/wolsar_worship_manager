import dayjs from "dayjs";
import type { CalendarEvent, Member, Profile } from "./types";
export const demoProfile: Profile = {
  id: 1,
  name: "Анна",
  surname: "Соколова",
  birthday_date: "1997-04-12",
  ministries: [
    {
      id: 1,
      name: "Прославление",
      church_name: "Церковь «Слово жизни»",
      access_level: "admin",
      permissions: [
        "view_schedule",
        "view_members",
        "self_signup",
        "manage_events",
        "manage_assignments",
        "use_assistant",
        "manage_members",
      ],
    },
  ],
};
export const demoMembers: Member[] = [
  {
    id: 1,
    name: "Анна",
    surname: "Соколова",
    access_level: "admin",
    roles: [{ id: 1, name: "Вокал", user_ministry_role_id: 11 }],
  },
  {
    id: 2,
    name: "Михаил",
    surname: "Орлов",
    access_level: "member",
    roles: [{ id: 2, name: "Клавиши", user_ministry_role_id: 22 }],
  },
  {
    id: 3,
    name: "София",
    surname: "Волкова",
    access_level: "coordinator",
    roles: [{ id: 1, name: "Вокал", user_ministry_role_id: 31 }],
  },
  {
    id: 4,
    name: "Даниил",
    surname: "Морозов",
    access_level: "member",
    roles: [{ id: 3, name: "Гитара", user_ministry_role_id: 43 }],
  },
  {
    id: 5,
    name: "Алексей",
    surname: "Белов",
    access_level: "member",
    roles: [{ id: 4, name: "Ударные", user_ministry_role_id: 54 }],
  },
];
export function demoEvents(month: string): CalendarEvent[] {
  const first = dayjs(month + "-01");
  return Array.from({ length: first.daysInMonth() }, (element, index) =>
    first.add(index, "day"),
  )
    .filter((date) => date.day() === 0)
    .map((date, index) => ({
      event_id: index + 1,
      event_name: "Воскресное служение",
      starts_at: date.hour(11).format(),
      additional_info:
        index === 0
          ? "Собираемся за час до начала. Возьмите наушники для репетиции."
          : "Встречаемся в основном зале.",
      rehearsal_at: date.subtract(1, "day").hour(18).format(),
      event_reminder_at: null,
      rehearsal_reminder_at: null,
      song_ids: [],
      role_slots: [1, 2, 3, 4].map((roleId, slotIndex) => ({
        id: index * 10 + slotIndex,
        ministry_role_id: roleId,
        slot_number: 1,
        user_ministry_role_id:
          index === 2 && roleId === 3
            ? null
            : roleId === 1
              ? index % 2
                ? 31
                : 11
              : [0, 0, 22, 43, 54][roleId],
        confirmation_status: index === 1 ? "pending" : "confirmed",
      })),
    }));
}
