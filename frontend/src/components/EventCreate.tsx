import DateTimeInput from "./DateTimeInput";
import dayjs from "dayjs";
import { eventKinds, inferEventKind } from "../eventKinds";
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Form,
  Input,
  Modal,
  Segmented,
  Select,
  Space,
  Switch,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { api } from "../api";
import {
  applyTemplate,
  builtinTemplates,
  numberSlots,
  type EventDraft,
  type EventTemplate,
} from "../eventTemplates";
import type { Member } from "../types";
import EventTeamFields, { type RoleOption } from "./EventTeamFields";
import EventTemplateEditor from "./EventTemplateEditor";

export default function EventCreate({
  open,
  ministryId,
  demo,
  canManageTemplates,
  members,
  onClose,
  onCreate,
}: {
  open: boolean;
  ministryId: number;
  demo: boolean;
  canManageTemplates: boolean;
  members: Member[];
  onClose: () => void;
  onCreate: (draft: EventDraft) => Promise<void>;
}) {
  const [form] = Form.useForm();
  const [mode, setMode] = useState("template");
  const [templates, setTemplates] = useState<EventTemplate[]>(builtinTemplates);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [selectedId, setSelectedId] = useState(builtinTemplates[0].id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState(false);
  const [editing, setEditing] = useState<EventTemplate>();
  const selected = templates.find((template) => template.id === selectedId);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setError("");
    setBusy(true);
    setMode("template");
    form.resetFields();
    const load = async () => {
      try {
        const [items, roleList] = demo
          ? [
              templates,
              Array.from(
                new Map(
                  members.flatMap((member) =>
                    member.roles.map(
                      (role) =>
                        [role.id, { id: role.id, name: role.name }] as const,
                    ),
                  ),
                ).values(),
              ),
            ]
          : await Promise.all([
              api<EventTemplate[]>(
                `/portal/ministries/${ministryId}/templates`,
              ),
              api<RoleOption[]>(`/portal/ministries/${ministryId}/roles`),
            ]);
        if (!active) return;
        setTemplates(items);
        setRoles(roleList);
        setSelectedId(items[0].id);
        form.setFieldsValue({
          ...applyTemplate(items[0]),
          event_kind: inferEventKind(items[0].name),
          reminders_enabled: true,
        });
      } catch (error) {
        if (active)
          setError(
            error instanceof Error
              ? error.message
              : "Не удалось загрузить шаблоны",
          );
      } finally {
        if (active) setBusy(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [open, ministryId, demo, form]);
  const choose = (id: string) => {
    setSelectedId(id);
    const template = templates.find((item) => item.id === id);
    if (template)
      form.setFieldsValue({
        ...applyTemplate(template, form.getFieldValue("starts_at")),
        event_kind: inferEventKind(template.name),
      });
  };
  const submit = async () => {
    try {
      const values = await form.validateFields();
      setBusy(true);
      setError("");
      if (values.rehearsal_at && values.rehearsal_at.isAfter(values.starts_at))
        throw new Error("Репетиция должна начинаться до события");
      await onCreate({
        event_name: values.event_name.trim(),
        event_kind: values.event_kind || inferEventKind(values.event_name),
        starts_at: values.starts_at.format(),
        timezone: "Europe/Saratov",
        additional_info: values.additional_info || null,
        rehearsal_at: values.rehearsal_at?.format() || null,
        reminders_enabled: values.reminders_enabled,
        role_slots: numberSlots(values.role_slots || []),
      });
      onClose();
    } catch (error) {
      if (error instanceof Error) setError(error.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Modal
        title="Создать событие"
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
        onOk={() => void submit()}
        confirmLoading={busy}
        okButtonProps={{ disabled: busy }}
        okText="Создать событие"
        cancelText="Отмена"
        width={720}
      >
        {error && (
          <Alert type="error" message={error} style={{ marginBottom: 16 }} />
        )}
        <Segmented
          block
          value={mode}
          options={[
            { label: "По шаблону", value: "template" },
            { label: "Своё событие", value: "custom" },
          ]}
          onChange={(value) => {
            setMode(value);
            setError("");
            if (value === "template") choose(selectedId);
            else
              form.setFieldsValue({
                event_name: "",
                additional_info: null,
                rehearsal_at: null,
                role_slots: (templates[0]?.role_slots || []).map((slot) => ({
                  ...slot,
                  user_ministry_role_id: null,
                })),
              });
          }}
        />
        {mode === "template" && (
          <div className="event-template-picker">
            <Select
              aria-label="Шаблон события"
              value={selectedId}
              onChange={choose}
              style={{ width: "100%" }}
              options={templates.map((template) => ({
                value: template.id,
                label:
                  template.name +
                  (template.builtin ? "" : " · шаблон служения"),
              }))}
            />
            {canManageTemplates && (
              <Space wrap>
                <Button
                  icon={<PlusOutlined />}
                  onClick={() => {
                    setEditing(undefined);
                    setEditor(true);
                  }}
                >
                  Новый шаблон
                </Button>
                <Button
                  type="text"
                  onClick={() => {
                    setEditing(selected);
                    setEditor(true);
                  }}
                >
                  {selected?.builtin ? "Создать копию" : "Настроить шаблон"}
                </Button>
              </Space>
            )}
            <p className="subtle">
              Название, репетицию и состав можно изменить для этого события.
            </p>
          </div>
        )}
        <Form
          name="event_create"
          form={form}
          layout="vertical"
          style={{ marginTop: 20 }}
          onValuesChange={(changed) => {
            if (
              changed.starts_at &&
              mode === "template" &&
              selected?.rehearsal_offset_minutes != null
            )
              form.setFieldValue(
                "rehearsal_at",
                changed.starts_at.subtract(
                  selected.rehearsal_offset_minutes,
                  "minute",
                ),
              );
          }}
        >
          <Form.Item
            name="event_name"
            label="Название события"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input maxLength={150} placeholder="Например, встреча команды" />
          </Form.Item>
          <div className="event-date-grid">
            <Form.Item
              name="event_kind"
              label="Вид собрания"
              rules={[{ required: true, message: "Выберите вид собрания" }]}
            >
              <Select options={eventKinds} />
            </Form.Item>
            <Form.Item
              name="starts_at"
              label="Дата и время события"
              rules={[
                { required: true, message: "Выберите дату и время" },
                {
                  validator: (rule, value) =>
                    !value || value.isAfter(dayjs())
                      ? Promise.resolve()
                      : Promise.reject(
                          new Error(
                            "Дата и время события должны быть в будущем",
                          ),
                        ),
                },
              ]}
            >
              <DateTimeInput
                minDate={dayjs().startOf("day")}
                style={{ width: "100%" }}
              />
            </Form.Item>
            <Form.Item name="rehearsal_at" label="Дата и время репетиции">
              <DateTimeInput style={{ width: "100%" }} />
            </Form.Item>
          </div>
          <Form.Item
            name="additional_info"
            label="Заметки и информация для команды"
          >
            <Input.TextArea rows={3} maxLength={10000} />
          </Form.Item>
          <h3>Кто служит</h3>
          <EventTeamFields roles={roles} members={members} />
          <Form.Item
            name="reminders_enabled"
            label="Напоминания о событии и репетиции"
            valuePropName="checked"
            extra="За день и за два часа — назначенным служителям с подключёнными уведомлениями."
            style={{ marginTop: 20 }}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
      <EventTemplateEditor
        open={editor}
        template={editing}
        ministryId={ministryId}
        demo={demo}
        roles={roles}
        members={members}
        onClose={() => setEditor(false)}
        onSaved={(template) => {
          setTemplates((current) => [
            ...current.filter((item) => item.id !== template.id),
            template,
          ]);
          setSelectedId(template.id);
          setMode("template");
          form.setFieldsValue(
            applyTemplate(template, form.getFieldValue("starts_at")),
          );
        }}
      />
    </>
  );
}
