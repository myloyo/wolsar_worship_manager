import { useState } from "react";
import { Alert, Button, Modal, Select, Space } from "antd";
import { api, json } from "../api";
import { eventKinds } from "../eventKinds";
import type { Member } from "../types";

export default function MemberEventKinds({
  member,
  ministryId,
  onChanged,
}: {
  member: Member;
  ministryId: number;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<number, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<number>();
  const save = async (roleId: number) => {
    setBusy(true);
    setError("");
    setSaved(undefined);
    try {
      await api(
        `/portal/ministries/${ministryId}/members/${member.id}/roles/${roleId}/event-kinds`,
        json("PUT", { allowed_event_kinds: values[roleId] || [] }),
      );
      setSaved(roleId);
      onChanged();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось сохранить ограничения",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button
        size="small"
        onClick={() => {
          setValues(
            Object.fromEntries(
              member.roles.map((role) => [
                role.user_ministry_role_id,
                role.allowed_event_kinds || [],
              ]),
            ),
          );
          setError("");
          setSaved(undefined);
          setOpen(true);
        }}
      >
        Виды собраний
      </Button>
      <Modal
        title={`${member.name} ${member.surname} · роли и собрания`}
        open={open}
        footer={null}
        onCancel={() => {
          if (!busy) setOpen(false);
        }}
      >
        <p>
          Выберите, на каких собраниях человек может служить в каждой роли.
          Пустой список — любые виды событий.
        </p>
        {error && <Alert type="error" message={error} />}
        {!member.roles.length && (
          <p>Сначала добавьте участнику роль служения.</p>
        )}
        {member.roles.map((role) => (
          <section key={role.user_ministry_role_id} style={{ marginTop: 20 }}>
            <h4>{role.name}</h4>
            <Select
              mode="multiple"
              allowClear
              placeholder="Любые виды событий"
              options={eventKinds}
              value={values[role.user_ministry_role_id] || []}
              disabled={busy}
              style={{ width: "100%" }}
              onChange={(value) => {
                setSaved(undefined);
                setValues((current) => ({
                  ...current,
                  [role.user_ministry_role_id]: value,
                }));
              }}
            />
            <Space style={{ marginTop: 8 }}>
              <Button
                disabled={busy}
                onClick={() => void save(role.user_ministry_role_id)}
              >
                Сохранить
              </Button>
              {saved === role.user_ministry_role_id && <span>Сохранено</span>}
            </Space>
          </section>
        ))}
      </Modal>
    </>
  );
}
