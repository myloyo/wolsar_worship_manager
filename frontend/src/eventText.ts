import dayjs from "dayjs";

export function readableEventNotes(text: string): string {
  return text.replace(
    /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})/g,
    (value) =>
      dayjs(value).isValid() ? dayjs(value).format("D MMMM, HH:mm") : value,
  );
}
