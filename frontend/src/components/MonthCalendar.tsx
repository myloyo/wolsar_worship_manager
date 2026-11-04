import { useState } from "react";
import { Empty, Modal, Spin } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import type { CalendarEvent } from "../types";

export default function MonthCalendar({
  month,
  events,
  busy,
  onEvent,
}: {
  month: Dayjs;
  events: CalendarEvent[];
  busy: boolean;
  onEvent: (event: CalendarEvent) => void;
}) {
  const [date, setDate] = useState<Dayjs | null>(null);
  const start = month.startOf("month");
  const offset = (start.day() + 6) % 7;
  const count = Math.ceil((offset + month.daysInMonth()) / 7) * 7;
  const days = Array.from({ length: count }, (value, index) =>
    start.subtract(offset, "day").add(index, "day"),
  );
  const daily = (day: Dayjs) =>
    events.filter((event) => dayjs(event.starts_at).isSame(day, "day"));
  return (
    <Spin spinning={busy}>
      <div className="month-calendar" aria-label="Календарь событий месяца">
        {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
          <div key={day} className="calendar-weekday">
            {day}
          </div>
        ))}
        {days.map((day) => {
          const items = daily(day);
          return (
            <button
              key={day.format("YYYY-MM-DD")}
              type="button"
              className={`calendar-day ${day.month() !== month.month() ? "outside-month" : ""} ${day.isSame(dayjs(), "day") ? "today" : ""}`}
              aria-label={`${day.format("D MMMM")}, событий: ${items.length}`}
              onClick={() => setDate(day)}
            >
              <strong>{day.date()}</strong>
              {items.slice(0, 3).map((event) => (
                <span className="calendar-event-preview" key={event.event_id}>
                  <time>{dayjs(event.starts_at).format("HH:mm")}</time>{" "}
                  <span className="calendar-event-title">
                    {event.event_name}
                  </span>
                </span>
              ))}
              {items.length > 3 && <small>Ещё {items.length - 3}</small>}
            </button>
          );
        })}
      </div>
      <Modal
        title={date?.format("D MMMM YYYY")}
        open={!!date}
        footer={null}
        onCancel={() => setDate(null)}
      >
        {date && !daily(date).length && (
          <Empty description="В этот день событий нет" />
        )}
        {date &&
          daily(date).map((event) => (
            <button
              key={event.event_id}
              className="calendar-event-link"
              onClick={() => {
                setDate(null);
                onEvent(event);
              }}
            >
              <strong>
                {dayjs(event.starts_at).format("HH:mm")} · {event.event_name}
              </strong>
              <span>Состав, репетиция, песни и одежда →</span>
            </button>
          ))}
      </Modal>
    </Spin>
  );
}
