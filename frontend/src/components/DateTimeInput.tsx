import { DatePicker, TimePicker } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import type { CSSProperties } from "react";

type Props = {
  value?: Dayjs | null;
  onChange?: (value: Dayjs | null) => void;
  style?: CSSProperties;
  id?: string;
  minDate?: Dayjs;
};
export default function DateTimeInput({
  value,
  onChange,
  style,
  id,
  minDate,
}: Props) {
  return (
    <div className="date-time-input" style={style}>
      <DatePicker
        id={id}
        minDate={minDate}
        value={value}
        format="DD.MM.YYYY"
        placeholder="Дата"
        needConfirm={false}
        placement="topLeft"
        popupAlign={{
          offset: [0, 0],
          overflow: { adjustX: true, adjustY: true, shiftX: 8, shiftY: 8 },
        }}
        popupClassName="compact-date-popup"
        onChange={(date) =>
          onChange?.(
            date
              ? date
                  .hour(value?.hour() ?? 0)
                  .minute(value?.minute() ?? 0)
                  .second(0)
              : null,
          )
        }
      />
      <TimePicker
        aria-label="Время"
        value={value}
        format="HH:mm"
        placeholder="Время"
        needConfirm={false}
        placement="topLeft"
        popupAlign={{
          offset: [0, 0],
          overflow: { adjustX: true, adjustY: true, shiftX: 8, shiftY: 8 },
        }}
        popupClassName="compact-date-popup"
        onChange={(time) =>
          onChange?.(
            time
              ? (value || dayjs().startOf("day"))
                  .hour(time.hour())
                  .minute(time.minute())
                  .second(0)
              : null,
          )
        }
      />
    </div>
  );
}
