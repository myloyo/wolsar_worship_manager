import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Input,
  Popconfirm,
  Spin,
  Tag,
  Upload,
  message,
} from "antd";
import {
  ArrowUpOutlined,
  PaperClipOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api, json } from "./api";
import type { ChatSession, Member } from "./types";

export default function Assistant({
  ministryId,
  month,
  demo,
  members,
  onApplied,
}: {
  ministryId: number;
  month: string;
  demo: boolean;
  members: Member[];
  onApplied: () => void;
}) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);
  const [notice, contextHolder] = message.useMessage();
  useEffect(() => {
    if (demo) return;
    let active = true;
    void api<ChatSession | null>(
      `/portal/assistant/sessions?ministry_id=${ministryId}&month=${month}`,
    )
      .then((latest) => {
        if (active) setSession(latest);
      })
      .catch((error) => notice.error((error as Error).message));
    void api<{ id: number; name: string }[]>(
      `/portal/ministries/${ministryId}/roles`,
    )
      .then((catalog) => {
        if (active) setRoles(catalog);
      })
      .catch((error) => notice.error((error as Error).message));
    return () => {
      active = false;
    };
  }, [ministryId, month, demo]);
  const ensureSession = async () => {
    if (session) return session;
    const created = await api<ChatSession>(
      "/portal/assistant/sessions",
      json("POST", { ministry_id: ministryId, month }),
    );
    setSession(created);
    return created;
  };
  const send = async (text = input) => {
    if (!text.trim() || busy) return;
    if (demo) {
      notice.info(
        "В примере отправка отключена. Войдите в свой аккаунт, чтобы подключить помощника.",
      );
      return;
    }
    setBusy(true);
    setFailure("");
    try {
      const current = await ensureSession();
      const updated = await api<ChatSession>(
        `/portal/assistant/sessions/${current.id}/messages`,
        json("POST", { message: text }),
      );
      setSession(updated);
      setInput("");
    } catch (error) {
      setFailure((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const apply = async () => {
    if (!session || busy) return;
    setBusy(true);
    try {
      await api(
        `/portal/assistant/sessions/${session.id}/apply`,
        json("POST", { revision: session.revision }),
      );
      notice.success("Расписание обновлено");
      setSession(null);
      onApplied();
    } catch (error) {
      notice.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const nameFor = (id: number) => {
    const person = members.find((member) =>
      member.roles.some((role) => role.user_ministry_role_id === id),
    );
    return person ? `${person.name} ${person.surname}` : `Участник #${id}`;
  };
  const roleNameFor = (id: number) =>
    roles.find((role) => role.id === id)?.name ??
    members.flatMap((member) => member.roles).find((role) => role.id === id)
      ?.name ??
    `Роль #${id}`;
  return (
    <aside className="assistant panel">
      {contextHolder}
      <div className="assistant-head">
        <span className="spark-icon">
          <ThunderboltOutlined />
        </span>
        <div>
          <strong>Помощник служения</strong>
          <span>Планируем вместе</span>
        </div>
        <Button
          type="text"
          icon={<PlusOutlined />}
          aria-label="Новый диалог"
          disabled={busy}
          onClick={() => {
            if (demo) {
              setSession(null);
              return;
            }
            setBusy(true);
            void api<ChatSession>(
              "/portal/assistant/sessions",
              json("POST", { ministry_id: ministryId, month }),
            )
              .then(setSession)
              .catch((error) => notice.error((error as Error).message))
              .finally(() => setBusy(false));
          }}
        />
      </div>
      <div className="chat-body" aria-live="polite">
        {!session?.messages.length && (
          <>
            <Tag className="quiet-tag">{dayjs(month).format("MMMM YYYY")}</Tag>
            <h3>
              Освободим время
              <br />
              для самого важного.
            </h3>
            <p>
              Помогу составить график, учесть прошлые назначения и распределить
              нагрузку.
            </p>
            <div className="chat-bubble assistant-bubble">
              Загрузите расписание за два прошлых месяца — таблицей или
              фотографией. Расскажите, что нужно запланировать.
            </div>
            <button
              className="prompt"
              disabled={busy}
              onClick={() => {
                setInput(
                  "Составь расписание на месяц с учётом истории за два предыдущих месяца. Если данных мало, сначала задай вопросы.",
                );
              }}
            >
              Составить график на месяц <span>↗</span>
            </button>
            <button
              className="prompt"
              disabled={busy}
              onClick={() =>
                setInput(
                  "Помоги добавить новое событие. Какие данные тебе нужны?",
                )
              }
            >
              Добавить событие <span>↗</span>
            </button>
          </>
        )}
        {session?.messages.map((item, index) => {
          let text = item.content;
          if (item.role === "assistant") {
            try {
              text = JSON.parse(text).reply;
            } catch {
              /* Keep plain messages readable. */
            }
          }
          return (
            <div
              className={`chat-bubble ${item.role === "user" ? "user-bubble" : "assistant-bubble"}`}
              key={index}
            >
              {text}
            </div>
          );
        })}
        {session?.proposal && (
          <div className="proposal">
            <strong>Черновик изменений</strong>
            {session.proposal.warnings.map((warning, index) => (
              <Alert key={index} type="warning" message={warning} />
            ))}
            {session.proposal.events.map((event, index) => (
              <div className="proposal-event" key={index}>
                <b>
                  {dayjs(event.starts_at).format("DD MMM, HH:mm")} ·{" "}
                  {event.event_name}
                </b>
                <p>
                  {event.assignments
                    .map(
                      (assignment) =>
                        `${roleNameFor(assignment.ministry_role_id)} — ${nameFor(assignment.user_ministry_role_id)}`,
                    )
                    .join(", ") || "Без назначений"}
                </p>
                {!!event.extra_role_ids?.length && (
                  <p>
                    Новые места без назначения:{" "}
                    {event.extra_role_ids.map(roleNameFor).join(", ")}
                  </p>
                )}
              </div>
            ))}
            {session.proposal.events.length > 0 && (
              <Popconfirm
                title="Применить этот черновик к календарю?"
                onConfirm={apply}
                okText="Применить"
                cancelText="Проверить ещё"
              >
                <Button type="primary" block disabled={busy}>
                  Применить {session.proposal.events.length} событий
                </Button>
              </Popconfirm>
            )}
          </div>
        )}
        {busy && (
          <div className="thinking">
            <Spin size="small" /> <span role="status">Помощник работает…</span>
          </div>
        )}
      </div>
      <div className="chat-compose">
        {failure && (
          <Alert
            type="error"
            showIcon
            message={failure}
            closable
            onClose={() => setFailure("")}
            style={{ marginBottom: 12 }}
          />
        )}
        <Input.TextArea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Что запланируем?"
          autoSize={{ minRows: 2, maxRows: 5 }}
          maxLength={6000}
          disabled={busy}
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              void send();
            }
          }}
        />
        <div className="compose-actions">
          <Upload
            accept=".xlsx,.csv,.txt,.png,.jpg,.jpeg,.webp"
            showUploadList={false}
            disabled={busy || demo}
            beforeUpload={(file) => {
              void (async () => {
                setBusy(true);
                try {
                  const current = await ensureSession();
                  const body = new FormData();
                  body.append("file", file);
                  const updated = await api<ChatSession>(
                    `/portal/assistant/sessions/${current.id}/files`,
                    { method: "POST", body },
                  );
                  setSession(updated);
                  notice.success("Файл добавлен");
                } catch (error) {
                  notice.error((error as Error).message);
                } finally {
                  setBusy(false);
                }
              })();
              return false;
            }}
          >
            <Button
              type="text"
              icon={<PaperClipOutlined />}
              disabled={busy || demo}
            >
              Вложения{" "}
              {session?.attachment_count ? `· ${session.attachment_count}` : ""}
            </Button>
          </Upload>
          <Button
            type="primary"
            shape="circle"
            icon={<ArrowUpOutlined />}
            aria-label="Отправить сообщение"
            disabled={busy || !input.trim()}
            onClick={() => void send()}
          />
        </div>
        <small>
          Изменения появятся в календаре после вашего подтверждения.
        </small>
      </div>
    </aside>
  );
}
