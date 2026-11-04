import { useState } from "react";
import { Alert, Button, Input, Modal, Space, Tag } from "antd";
import { api, json } from "../api";

type Role = { id: number; name: string };
export default function MinistryRoles({
  ministryId,
  onChanged,
}: {
  ministryId: number;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<Role[]>([]);
  const show = async () => {
    setOpen(true);
    setError("");
    setBusy(true);
    try {
      setRoles(await api(`/portal/ministries/${ministryId}/roles`));
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось загрузить роли",
      );
    } finally {
      setBusy(false);
    }
  };
  const add = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const role = await api<Role>(
        `/portal/ministries/${ministryId}/roles`,
        json("POST", { name: name.trim() }),
      );
      setRoles((current) =>
        [...current, role].sort((a, b) => a.name.localeCompare(b.name, "ru")),
      );
      setName("");
      onChanged();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось добавить роль",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <p className="subtle">
        Новые участники регистрируются на сайте и подают заявку в команду. После
        одобрения они появятся в списке.
      </p>
      <Button onClick={() => void show()}>Роли команды</Button>
      <Modal
        title="Роли команды"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
      >
        <p className="subtle">
          Эти роли доступны в заявках и расписании. Права администратора
          назначаются отдельно.
        </p>
        {error && <Alert type="error" message={error} />}
        <Space wrap style={{ marginBottom: 20 }}>
          {roles.map((role) => (
            <Tag key={role.id}>{role.name}</Tag>
          ))}
        </Space>
        <Space.Compact style={{ width: "100%" }}>
          <Input
            aria-label="Название новой роли"
            placeholder="Например, Танцы"
            maxLength={100}
            value={name}
            onChange={(event) => setName(event.target.value)}
            onPressEnter={() => void add()}
          />
          <Button
            loading={busy}
            disabled={!name.trim()}
            onClick={() => void add()}
          >
            Добавить роль
          </Button>
        </Space.Compact>
      </Modal>
    </>
  );
}
