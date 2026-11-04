export const eventKinds = [
  { value: "sunday", label: "Воскресное собрание" },
  { value: "praise", label: "Вечер хвалы и молитвы" },
  { value: "prayer", label: "Молитва" },
  { value: "leaders", label: "Общее лидерское" },
  { value: "other", label: "Другое событие" },
];
export function inferEventKind(name: string): string {
  const text = name.toLocaleLowerCase("ru");
  if (text.includes("хвалы") || text.includes("вхм")) return "praise";
  if (text.includes("лидер") || text.trim() === "ол") return "leaders";
  if (text.includes("молитв")) return "prayer";
  if (text.includes("воскрес")) return "sunday";
  return "other";
}
export function roleAllowsEvent(
  role: { allowed_event_kinds?: string[] },
  kind: string,
) {
  return (
    !role.allowed_event_kinds?.length || role.allowed_event_kinds.includes(kind)
  );
}
