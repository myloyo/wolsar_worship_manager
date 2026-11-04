import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { Tooltip } from "antd";

export default function AssignmentStatus({ status }: { status: string }) {
  const confirmed = status === "confirmed";
  const replacement = status === "replacement";
  const label = replacement
    ? "Запрошена замена"
    : confirmed
      ? "Участие подтверждено"
      : "Ожидает ответа";
  return (
    <Tooltip title={label} trigger={["hover", "focus", "click"]}>
      <span
        className={`assignment-status ${confirmed ? "confirmed" : "pending"}`}
        role="img"
        aria-label={label}
        tabIndex={0}
      >
        {replacement ? (
          <SwapOutlined aria-hidden />
        ) : confirmed ? (
          <CheckCircleOutlined aria-hidden />
        ) : (
          <ClockCircleOutlined aria-hidden />
        )}
      </span>
    </Tooltip>
  );
}
