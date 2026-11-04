import { describe, expect, it } from "vitest";
import { inferEventKind, roleAllowsEvent } from "./eventKinds";
import { readableEventNotes } from "./eventText";

describe("Виды собраний", () => {
  it.each([
    ["Первое воскресное собрание", "sunday"],
    ["Воскресная молитва", "prayer"],
    ["Вечер хвалы и молитвы", "praise"],
    ["ОЛ", "leaders"],
    ["Конференция", "other"],
  ])("определяет вид %s", (name, kind) =>
    expect(inferEventKind(name)).toBe(kind),
  );
  it("пустой список разрешает все виды, выбранные виды строго ограничивают назначения", () => {
    expect(roleAllowsEvent({}, "other")).toBe(true);
    expect(roleAllowsEvent({ allowed_event_kinds: [] }, "sunday")).toBe(true);
    expect(roleAllowsEvent({ allowed_event_kinds: ["prayer"] }, "sunday")).toBe(
      false,
    );
    expect(roleAllowsEvent({ allowed_event_kinds: ["prayer"] }, "prayer")).toBe(
      true,
    );
  });
  it("показывает время в заметках без технической строки даты", () => {
    const result = readableEventNotes(
      "Окончание: 2026-11-08T09:40:00+04:00.\nБелый верх",
    );
    expect(result).not.toContain("T09:40");
    expect(result).toContain("Белый верх");
  });
});
