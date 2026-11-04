import { useState } from "react";
import { Alert, Button, Modal, Select } from "antd";
import { api, json } from "../api";
import type { Member } from "../types";

export default function MemberRoles({
  ministryId,
  member,
  onChanged,
}: {
  ministryId: number;
  member: Member;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);
  const [roleId, setRoleId] = useState<number>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const show = async () => {
    setOpen(true);
    setRoleId(undefined);
    setError("");
    setRoles([]);
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
  const save = async () => {
    if (!roleId) return;
    setBusy(true);
    setError("");
    try {
      await api(
        `/portal/ministries/${ministryId}/members/${member.id}/roles`,
        json("POST", { ministry_role_id: roleId }),
      );
      onChanged();
      setOpen(false);
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
      <Button size="small" onClick={() => void show()}>
        Добавить роль
      </Button>
      <Modal
        title={`Роль: ${member.name} ${member.surname}`}
        open={open}
        onCancel={() => {
          if (!busy) setOpen(false);
        }}
        onOk={() => void save()}
        okText="Добавить"
        cancelText="Отмена"
        confirmLoading={busy}
        okButtonProps={{ disabled: busy || !roleId }}
      >
        <p>
          Роль в служении добавится к существующим. Уровень доступа сохранится.
        </p>
        {error && (
          <Alert type="error" message={error} style={{ marginBottom: 16 }} />
        )}
        <Select
          style={{ width: "100%" }}
          placeholder="Выберите роль"
          value={roleId}
          loading={busy}
          disabled={busy}
          onChange={setRoleId}
          notFoundContent="Нет доступных ролей"
          options={roles
            .filter(
              (role) => !member.roles.some((current) => current.id === role.id),
            )
            .map((role) => ({ value: role.id, label: role.name }))}
        />
      </Modal>
    </>
  );
}
