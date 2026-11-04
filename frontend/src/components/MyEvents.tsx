import { useEffect, useState } from "react";
import { Alert, Button, Empty, Modal, Popconfirm, Space, Tag } from "antd";
import NotificationSettings from "./NotificationSettings";
import dayjs from "dayjs";
import { readableEventNotes } from "../eventText";
import { api, json } from "../api";
import { demoEvents } from "../demo";

type Assignment = {
  songs_text?: string;
  clothing_text?: string;
  slot_id: number;
  event_id: number;
  event_name: string;
  church_name: string;
  ministry_name: string;
  role_name: string;
  starts_at: string;
  rehearsal_at: string | null;
  additional_info: string | null;
  status: string;
  revision: string;
};
export default function MyEvents({
  demo,
  onChanged,
  onOpen,
}: {
  demo: boolean;
  onChanged: () => void;
  onOpen: (eventId: number) => void;
}) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [items, setItems] = useState<Assignment[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      const example = demoEvents(dayjs().format("YYYY-MM"))[1];
      setItems(
        demo
          ? [
              {
                slot_id: 1,
                event_id: example.event_id,
                event_name: example.event_name,
                church_name: "Церковь «Слово жизни»",
                ministry_name: "Прославление",
                role_name: "Вокал",
                starts_at: example.starts_at,
                rehearsal_at: example.rehearsal_at,
                additional_info: example.additional_info,
                status: "pending",
                revision: "20261101000000000000",
              },
            ]
          : await api<Assignment[]>("/portal/me/assignments"),
      );
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось загрузить события",
      );
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void load();
    if (demo) return;
    const refresh = () => {
      if (!document.hidden) void load();
    };
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 30000);
    return () => {
      window.removeEventListener("focus", refresh);
      window.clearInterval(timer);
    };
  }, [demo]);
  const respond = async (item: Assignment, accept: boolean) => {
    if (demo) {
      setItems((current) =>
        accept
          ? current.map((row) =>
              row.slot_id === item.slot_id
                ? { ...row, status: "confirmed" }
                : row,
            )
          : current.map((row) =>
              row.slot_id === item.slot_id
                ? { ...row, status: "replacement" }
                : row,
            ),
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(
        `/portal/me/assignments/${item.slot_id}`,
        json("PUT", { accept, revision: item.revision }),
      );
      await load();
      onChanged();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось сохранить ответ",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section>
      <div className="page-heading">
        <div>
          <span className="eyebrow">УЧАСТИЕ В СЛУЖЕНИИ</span>
          <h1>Доступность</h1>
          <p>
            Ваши назначения на служения. Подтвердите участие или сообщите, что
            не сможете.
          </p>
        </div>
        <Space wrap>
          <Button onClick={() => setShowNotifications(true)}>
            Настройки уведомлений
          </Button>
          <Button loading={busy} onClick={() => void load()}>
            Обновить
          </Button>
        </Space>
      </div>
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      {!items.length && !busy && (
        <Empty description="Предстоящих назначений пока нет" />
      )}
      <div className="my-events-list">
        {items.map((item) => (
          <article className="my-event-card" key={item.slot_id}>
            <p className="subtle">
              {item.church_name} · {item.ministry_name}
            </p>
            <h2>
              <button
                className="event-title-link"
                onClick={() => onOpen(item.event_id)}
              >
                {item.event_name}
              </button>
            </h2>
            <p>{dayjs(item.starts_at).format("D MMMM YYYY, HH:mm")}</p>
            <Space wrap className="my-event-status">
              <Tag>{item.role_name}</Tag>
              <Tag>
                {item.status === "replacement"
                  ? "Замена запрошена"
                  : item.status === "confirmed"
                    ? "Подтверждено"
                    : "Ждёт вашего ответа"}
              </Tag>
            </Space>
            {item.rehearsal_at && (
              <p>
                Репетиция: {dayjs(item.rehearsal_at).format("D MMMM, HH:mm")}
              </p>
            )}
            {item.additional_info && (
              <p className="event-notes">
                {readableEventNotes(item.additional_info)}
              </p>
            )}
            {item.songs_text && (
              <>
                <strong>Песни</strong>
                <p className="event-notes">{item.songs_text}</p>
              </>
            )}
            {item.clothing_text && (
              <>
                <strong>Одежда</strong>
                <p className="event-notes">{item.clothing_text}</p>
              </>
            )}
            <Space wrap style={{ marginTop: 20 }}>
              {item.status === "pending" && (
                <Button
                  type="primary"
                  disabled={busy}
                  onClick={() => void respond(item, true)}
                >
                  Подтвердить
                </Button>
              )}
              {item.status !== "replacement" ? (
                <Popconfirm
                  title="Запросить замену?"
                  description="Координатор и админы получат уведомление. Вы остаётесь в составе до назначения замены."
                  okText="Запросить"
                  cancelText="Отмена"
                  onConfirm={() => respond(item, false)}
                >
                  <Button danger disabled={busy}>
                    Запросить замену
                  </Button>
                </Popconfirm>
              ) : (
                <p className="subtle">
                  Координатор и админы уведомлены. Ожидайте назначения замены.
                </p>
              )}
              <Button onClick={() => onOpen(item.event_id)}>
                Открыть событие
              </Button>
            </Space>
          </article>
        ))}
      </div>
      <Modal
        title="Настройки уведомлений"
        open={showNotifications}
        onCancel={() => setShowNotifications(false)}
        footer={null}
      >
        <NotificationSettings demo={demo} />
      </Modal>
    </section>
  );
}
