import type { Dayjs } from "dayjs";
export type TeamSlot = {
  ministry_role_id: number;
  slot_number: number;
  user_ministry_role_id: number | null;
};
export type EventTemplate = {
  id: string;
  name: string;
  builtin: boolean;
  additional_info: string | null;
  rehearsal_offset_minutes: number | null;
  role_slots: TeamSlot[];
};
export type EventDraft = {
  event_kind?: string;
  event_name: string;
  starts_at: string;
  rehearsal_at: string | null;
  reminders_enabled: boolean;
  timezone: string;
  additional_info: string | null;
  role_slots: TeamSlot[];
};
export const builtinTemplates: EventTemplate[] = [
  ["sunday-meeting", "Воскресное собрание"],
  ["sunday-prayer", "Воскресная молитва"],
  ["leaders-meeting", "Общее лидерское собрание"],
  ["praise-and-prayer", "Вечер хвалы и молитвы"],
].map(([id, name]) => ({
  id,
  name,
  builtin: true,
  additional_info: null,
  rehearsal_offset_minutes: null,
  role_slots: [],
}));
export function applyTemplate(template: EventTemplate, startsAt?: Dayjs) {
  return {
    event_name: template.name,
    additional_info: template.additional_info,
    role_slots: template.role_slots.map((slot) => ({ ...slot })),
    rehearsal_at:
      startsAt && template.rehearsal_offset_minutes !== null
        ? startsAt.subtract(template.rehearsal_offset_minutes, "minute")
        : null,
  };
}
export function numberSlots(slots: TeamSlot[]): TeamSlot[] {
  const counts = new Map<number, number>();
  return slots.map((slot) => {
    const number = (counts.get(slot.ministry_role_id) || 0) + 1;
    counts.set(slot.ministry_role_id, number);
    return {
      ...slot,
      slot_number: number,
      user_ministry_role_id: slot.user_ministry_role_id ?? null,
    };
  });
}
