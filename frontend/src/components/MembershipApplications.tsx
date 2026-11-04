import { useEffect, useState } from "react";
import { Alert, Button, Empty, Input, Select, Space, Tag } from "antd";
import { api, json } from "../api";
type Request = {
  id: number;
  user_id: number;
  name: string;
  surname: string;
  role_ids: number[];
  message: string | null;
  created_at: string;
};
export default function MembershipApplications({
  ministryId,
  onChanged,
}: {
  ministryId: number;
  onChanged: () => void;
}) {
  const [items, setItems] = useState<Request[]>([]);
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);
  const [selected, setSelected] = useState<Record<number, number[]>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      const [requests, catalog] = await Promise.all([
        api<Request[]>(`/portal/ministries/${ministryId}/applications`),
        api<{ id: number; name: string }[]>(
          `/portal/ministries/${ministryId}/roles`,
        ),
      ]);
      setItems(requests);
      setRoles(catalog);
      setSelected(
        Object.fromEntries(requests.map((item) => [item.id, item.role_ids])),
      );
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось загрузить заявки",
      );
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void load();
  }, [ministryId]);
  const decide = async (id: number, approve: boolean) => {
    setBusy(true);
    setError("");
    try {
      await api(
        `/portal/ministries/${ministryId}/applications/${id}`,
        json("PUT", {
          approve,
          role_ids: selected[id] || [],
          message: notes[id] || null,
        }),
      );
      await load();
      onChanged();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось рассмотреть заявку",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="membership-applications">
      <Space wrap style={{ justifyContent: "space-between", width: "100%" }}>
        <h3>
          Заявки в команду <Tag>{items.length}</Tag>
        </h3>
        <Button size="small" loading={busy} onClick={() => void load()}>
          Обновить заявки
        </Button>
      </Space>
      {error && <Alert type="error" message={error} />}
      {!items.length && <p className="subtle">Новых заявок пока нет.</p>}
      {items.map((item) => (
        <article className="application-card" key={item.id}>
          <strong>
            {item.name} {item.surname}
          </strong>
          {item.message && <p className="event-notes">{item.message}</p>}
          <p className="subtle">
            Назначьте роли участника при одобрении. Администратором он
            автоматически не станет.
          </p>
          <Select
            mode="multiple"
            aria-label={`Роли для ${item.name} ${item.surname}`}
            value={selected[item.id]}
            onChange={(value) =>
              setSelected((current) => ({ ...current, [item.id]: value }))
            }
            style={{ width: "100%", marginBottom: 12 }}
            options={roles.map((role) => ({
              value: role.id,
              label: role.name,
            }))}
          />
          <Input.TextArea
            placeholder="Комментарий к решению (необязательно)"
            maxLength={2000}
            value={notes[item.id] || ""}
            onChange={(event) =>
              setNotes((current) => ({
                ...current,
                [item.id]: event.target.value,
              }))
            }
          />
          <Space style={{ marginTop: 12 }}>
            <Button
              type="primary"
              disabled={busy}
              onClick={() => void decide(item.id, true)}
            >
              Принять в команду
            </Button>
            <Button disabled={busy} onClick={() => void decide(item.id, false)}>
              Отклонить
            </Button>
          </Space>
        </article>
      ))}
    </section>
  );
}
