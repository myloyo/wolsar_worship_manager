import { expect, it } from "vitest";
import dayjs from "dayjs";
import {
  applyTemplate,
  numberSlots,
  type EventTemplate,
} from "./eventTemplates";
it("copies defaults without mutating the template and keeps notes intact", () => {
  // Arrange
  const template: EventTemplate = {
    id: "a",
    name: "Meeting",
    builtin: false,
    additional_info: "Song one\n\nSong two 🎵",
    rehearsal_offset_minutes: 120,
    role_slots: [
      { ministry_role_id: 1, slot_number: 1, user_ministry_role_id: 2 },
    ],
  };
  const starts = dayjs("2026-11-01T11:00:00");
  // Act
  const values = applyTemplate(template, starts);
  values.role_slots[0].user_ministry_role_id = null;
  // Assert
  expect(values.rehearsal_at?.format("HH:mm")).toBe("09:00");
  expect(values.additional_info).toBe("Song one\n\nSong two 🎵");
  expect(template.role_slots[0].user_ministry_role_id).toBe(2);
});
it("numbers multiple places within each role independently", () => {
  // Arrange
  const slots = [1, 2, 1].map((id) => ({
    ministry_role_id: id,
    slot_number: 1,
    user_ministry_role_id: null,
  }));
  // Act
  const numbered = numberSlots(slots);
  // Assert
  expect(numbered.map((slot) => slot.slot_number)).toEqual([1, 1, 2]);
});
