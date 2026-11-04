import { useEffect, useState } from "react";
import { Alert, Form, Input, InputNumber, Modal } from "antd";
import { api, json } from "../api";
import { numberSlots, type EventTemplate } from "../eventTemplates";
import type { Member } from "../types";
import EventTeamFields, { type RoleOption } from "./EventTeamFields";
export default function EventTemplateEditor({
  open,
  template,
  ministryId,
  demo,
  roles,
  members,
  onClose,
  onSaved,
}: {
  open: boolean;
  template?: EventTemplate;
  ministryId: number;
  demo: boolean;
  roles: RoleOption[];
  members: Member[];
  onClose: () => void;
  onSaved: (template: EventTemplate) => void;
}) {
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      form.resetFields();
      form.setFieldsValue(template || { role_slots: [] });
      setError("");
    }
  }, [open, template, form]);
  const save = async () => {
    try {
      const values = await form.validateFields();
      setBusy(true);
      setError("");
      const payload = {
        ...values,
        name: values.name.trim(),
        additional_info: values.additional_info || null,
        rehearsal_offset_minutes: values.rehearsal_offset_minutes ?? null,
        role_slots: numberSlots(values.role_slots || []),
      };
      const update = template && !template.builtin;
      const saved = demo
        ? ({
            ...payload,
            id: update ? template.id : `demo-${Date.now()}`,
            builtin: false,
          } as EventTemplate)
        : await api<EventTemplate>(
            `/portal/ministries/${ministryId}/templates${update ? `/${template.id}` : ""}`,
            json(update ? "PUT" : "POST", payload),
          );
      onSaved(saved);
      onClose();
    } catch (error) {
      if (error instanceof Error) setError(error.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title={
        template && !template.builtin
          ? "Настроить шаблон"
          : "Новый шаблон события"
      }
      open={open}
      style={{ top: 24 }}
      styles={{
        body: {
          maxHeight: "calc(100dvh - 210px)",
          overflowY: "auto",
          paddingRight: 6,
        },
      }}
      onCancel={onClose}
      onOk={() => void save()}
      confirmLoading={busy}
      okText="Сохранить шаблон"
      cancelText="Отмена"
      width={680}
    >
      <p className="subtle">
        Шаблон доступен всему служению. Дату события вы выберете позже.
        Изменение шаблона не меняет уже созданные события.
      </p>
      {error && <Alert type="error" message={error} />}
      <Form name="event_template" form={form} layout="vertical">
        <Form.Item
          name="name"
          label="Название события"
          rules={[{ required: true, whitespace: true }]}
        >
          <Input maxLength={150} />
        </Form.Item>
        <Form.Item
          name="rehearsal_offset_minutes"
          label="Репетиция за … минут до события"
          extra="Оставьте пустым, если репетиции нет."
        >
          <InputNumber
            min={0}
            max={10080}
            precision={0}
            style={{ width: "100%" }}
          />
        </Form.Item>
        <Form.Item
          name="additional_info"
          label="Заметки и информация для команды"
        >
          <Input.TextArea rows={3} maxLength={10000} />
        </Form.Item>
        <h3>Кто служит</h3>
        <EventTeamFields roles={roles} members={members} />
      </Form>
    </Modal>
  );
}
