import DateTimeInput from "./DateTimeInput";
import AssignmentStatus from "./AssignmentStatus";
import { useEffect, useState } from "react";
import {
  Button,
  Alert,
  Select,
  Descriptions,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Space,
  Switch,
  message,
} from "antd";
import dayjs from "dayjs";
import { readableEventNotes } from "../eventText";
import { eventKinds, roleAllowsEvent } from "../eventKinds";
import { api, json } from "../api";
import type { CalendarEvent, Member, Profile, Slot } from "../types";

type Props = {
  event: CalendarEvent | null;
  members: Member[];
  profile: Profile;
  canManage: boolean;
  canAssign: boolean;
  ministryId: number | undefined;
  onAssign: (slot: Slot, value: number | undefined) => Promise<void>;
  canParticipate: boolean;
  demo: boolean;
  onClose: () => void;
  onSaved: () => void;
};
export default function EventDetails({
  event,
  members,
  profile,
  canManage,
  canAssign,
  ministryId,
  onAssign,
  canParticipate,
  demo,
  onClose,
  onSaved,
}: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [roles, setRoles] = useState<{ id: number; name: string }[]>([]);
  const [roleId, setRoleId] = useState<number>();
  const [personRoleId, setPersonRoleId] = useState<number>();
  const [failure, setFailure] = useState("");
  const [canEditContent, setCanEditContent] = useState(false);
  const [songsText, setSongsText] = useState("");
  const [clothingText, setClothingText] = useState("");
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [notificationsLoading, setNotificationsLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setNotificationsLoading(true);
    if (!event) return;
    if (demo) {
      setNotificationsEnabled(true);
      setNotificationsLoading(false);
      return;
    }
    void api<{ enabled: boolean }>(
      `/portal/events/${event.event_id}/notifications`,
    )
      .then((result) => {
        if (active) setNotificationsEnabled(result.enabled);
      })
      .catch((error) => {
        if (active) setFailure(error.message);
      })
      .finally(() => {
        if (active) setNotificationsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [event?.event_id, demo]);
  const toggleNotifications = async (enabled: boolean) => {
    if (!event || demo) return;
    setNotificationsLoading(true);
    try {
      await api(
        `/portal/events/${event.event_id}/notifications`,
        json("PUT", { enabled }),
      );
      setNotificationsEnabled(enabled);
    } catch (error) {
      notice.error((error as Error).message);
    } finally {
      setNotificationsLoading(false);
    }
  };
  const deleteEvent = async () => {
    if (!event || demo) return;
    setSaving(true);
    try {
      await api(`/portal/events/${event.event_id}`, { method: "DELETE" });
      notice.success("Событие удалено");
      finish();
    } catch (error) {
      notice.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };
  useEffect(() => {
    setCanEditContent(false);
    setSongsText(event?.songs_text || "");
    setClothingText(event?.clothing_text || "");
    if (!event || demo) return;
    let active = true;
    void api<{ can_edit: boolean }>(
      `/portal/events/${event.event_id}/content-permission`,
    )
      .then((result) => {
        if (active) setCanEditContent(result.can_edit);
      })
      .catch((error) => {
        if (active) setFailure(error.message);
      });
    return () => {
      active = false;
    };
  }, [event?.event_id, event?.content_revision, demo]);
  const saveContent = async () => {
    if (!event) return;
    setSaving(true);
    setFailure("");
    try {
      await api(
        `/portal/events/${event.event_id}/content`,
        json("PUT", {
          revision: event.content_revision || 0,
          songs_text: songsText,
          clothing_text: clothingText,
        }),
      );
      notice.success(
        "Информация сохранена. Уведомления поставлены в очередь участникам",
      );
      finish();
    } catch (error) {
      setFailure(
        error instanceof Error ? error.message : "Не удалось сохранить",
      );
    } finally {
      setSaving(false);
    }
  };
  const setKind = async (kind: string) => {
    if (!event || demo) return;
    setSaving(true);
    setFailure("");
    try {
      await api(
        `/portal/events/${event.event_id}/kind`,
        json("PUT", { event_kind: kind }),
      );
      finish();
    } catch (error) {
      setFailure(
        error instanceof Error ? error.message : "Не удалось сохранить",
      );
    } finally {
      setSaving(false);
    }
  };
  useEffect(() => {
    setRoleId(undefined);
    setPersonRoleId(undefined);
    setFailure("");
    if (!event || !ministryId) return;
    if (demo) {
      setRoles([
        ...new Map(
          members.flatMap((member) =>
            member.roles.map(
              (role) => [role.id, { id: role.id, name: role.name }] as const,
            ),
          ),
        ).values(),
      ]);
    } else {
      void api<{ id: number; name: string }[]>(
        `/portal/ministries/${ministryId}/roles`,
      )
        .then(setRoles)
        .catch((error) => setFailure(error.message));
    }
  }, [event?.event_id, ministryId, demo]);
  const addParticipant = async () => {
    if (!event || !roleId) return;
    if (demo) {
      notice.info("Назначения в демо не сохраняются");
      return;
    }
    setSaving(true);
    setFailure("");
    try {
      await api(
        `/portal/events/${event.event_id}/role-slots`,
        json("POST", {
          ministry_role_id: roleId,
          user_ministry_role_id: personRoleId ?? null,
        }),
      );
      notice.success(
        personRoleId
          ? "Служитель назначен на событие"
          : "Место добавлено в состав",
      );
      finish();
    } catch (error) {
      setFailure(
        error instanceof Error
          ? error.message
          : "Не удалось назначить служителя",
      );
    } finally {
      setSaving(false);
    }
  };
  const [notice, contextHolder] = message.useMessage();
  useEffect(() => {
    if (event)
      form.setFieldsValue({
        rehearsal_at: event.rehearsal_at ? dayjs(event.rehearsal_at) : null,
        remindEvent: !!event.event_reminder_at,
        remindRehearsal: !!event.rehearsal_reminder_at,
      });
  }, [
    event?.event_id,
    event?.rehearsal_at,
    event?.event_reminder_at,
    event?.rehearsal_reminder_at,
    form,
  ]);
  const finish = () => {
    onSaved();
    onClose();
  };
  const saveSchedule = async () => {
    if (!event) return;
    setSaving(true);
    try {
      const values = await form.validateFields();
      if (values.remindRehearsal && !values.rehearsal_at) {
        notice.error("Сначала укажите дату репетиции");
        return;
      }
      if (demo) {
        notice.info("Настройки в демо не сохраняются");
        return;
      }
      await api(
        `/events/${event.event_id}/schedule`,
        json("PUT", {
          rehearsal_at: values.rehearsal_at?.format() ?? null,
          event_reminder_at: values.remindEvent
            ? dayjs(event.starts_at).subtract(1, "day").format()
            : null,
          rehearsal_reminder_at:
            values.remindRehearsal && values.rehearsal_at
              ? values.rehearsal_at.subtract(1, "day").format()
              : null,
        }),
      );
      finish();
    } catch (error) {
      if (error instanceof Error) notice.error(error.message);
    } finally {
      setSaving(false);
    }
  };
  const participation = async (slot: Slot, withdraw = false) => {
    if (!event) return;
    if (demo) {
      notice.info("Участие в демо не сохраняется");
      return;
    }
    setSaving(true);
    try {
      if (withdraw) {
        const assignments = await api<{ slot_id: number; revision: string }[]>(
          "/portal/me/assignments",
        );
        const assignment = assignments.find((item) => item.slot_id === slot.id);
        if (!assignment)
          throw new Error("Назначение изменилось. Обновите событие");
        await api(
          `/portal/me/assignments/${slot.id}`,
          json("PUT", { accept: false, revision: assignment.revision }),
        );
      } else
        await api(
          `/events/${event.event_id}/participation${withdraw ? "/" + slot.ministry_role_id : ""}`,
          withdraw
            ? { method: "DELETE" }
            : json("PUT", { ministry_role_id: slot.ministry_role_id }),
        );
      finish();
    } catch (error) {
      notice.error((error as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Drawer
      title={event?.event_name}
      open={!!event}
      onClose={onClose}
      width={430}
    >
      {contextHolder}
      <section style={{ marginBottom: 24 }}>
        <Space wrap>
          <Switch
            aria-label="Уведомления об этом событии"
            checked={notificationsEnabled}
            loading={notificationsLoading}
            disabled={demo || notificationsLoading}
            onChange={(value) => void toggleNotifications(value)}
          />
          <span>Уведомления об этом событии</span>
        </Space>
        <p className="subtle">
          Для своих назначений включены по умолчанию. Доставку на устройство
          можно включить в «Доступности» → «Настройки уведомлений».
        </p>
      </section>
      <Descriptions
        column={1}
        items={[
          {
            key: "date",
            label: "Начало",
            children: dayjs(event?.starts_at).format("DD MMMM YYYY, HH:mm"),
          },
          {
            key: "rehearsal",
            label: "Репетиция",
            children: event?.rehearsal_at
              ? dayjs(event.rehearsal_at).format("DD MMMM, HH:mm")
              : "Не назначена",
          },
          {
            key: "notes",
            label: "Заметки",
            children: (
              <div className="event-notes">
                {event?.additional_info
                  ? readableEventNotes(event.additional_info)
                  : "Нет заметок"}
              </div>
            ),
          },
        ]}
      />
      <h3>Вид собрания</h3>
      {canManage ? (
        <Select
          style={{ width: "100%" }}
          options={eventKinds}
          disabled={saving || demo}
          value={event?.event_kind || "other"}
          onChange={(value) => void setKind(value)}
        />
      ) : (
        <p>
          {eventKinds.find((kind) => kind.value === event?.event_kind)?.label ||
            "Другое событие"}
        </p>
      )}
      <h3>Песни и одежда</h3>
      {canEditContent ? (
        <>
          <label htmlFor="event-songs">Список песен</label>
          <Input.TextArea
            id="event-songs"
            rows={5}
            maxLength={10000}
            value={songsText}
            onChange={(change) => setSongsText(change.target.value)}
          />
          <label htmlFor="event-clothing">Одежда</label>
          <Input.TextArea
            id="event-clothing"
            rows={3}
            maxLength={4000}
            value={clothingText}
            onChange={(change) => setClothingText(change.target.value)}
          />
          <Button
            style={{ marginTop: 12 }}
            loading={saving}
            onClick={() => void saveContent()}
          >
            Сохранить и уведомить участников
          </Button>
        </>
      ) : (
        <>
          <strong>Список песен</strong>
          <p className="event-notes">
            {event?.songs_text || "Ведущий ещё не добавил список"}
          </p>
          <strong>Одежда</strong>
          <p className="event-notes">
            {event?.clothing_text || "Пока не указана"}
          </p>
          <p className="subtle">
            Изменяет назначенный на это событие ведущий вокалист.
          </p>
        </>
      )}
      <h3>Участники события</h3>
      {failure && (
        <Alert type="error" message={failure} style={{ marginBottom: 16 }} />
      )}
      {canAssign && (
        <section className="event-participant-editor">
          <h4>Добавить место в составе</h4>
          <Select
            aria-label="Роль на событии"
            placeholder="Выберите роль"
            value={roleId}
            showSearch
            optionFilterProp="label"
            style={{ width: "100%", marginBottom: 12 }}
            options={roles.map((role) => ({
              value: role.id,
              label: role.name,
            }))}
            onChange={(value) => {
              setRoleId(value);
              setPersonRoleId(undefined);
            }}
          />
          <Select
            aria-label="Служитель на событии"
            placeholder="Служитель — можно выбрать позже"
            value={personRoleId}
            disabled={!roleId}
            showSearch
            optionFilterProp="label"
            style={{ width: "100%", marginBottom: 12 }}
            onChange={setPersonRoleId}
            options={members.flatMap((member) =>
              member.roles
                .filter(
                  (role) =>
                    role.id === roleId &&
                    roleAllowsEvent(role, event?.event_kind || "other"),
                )
                .map((role) => ({
                  value: role.user_ministry_role_id,
                  label: `${member.name} ${member.surname}`,
                })),
            )}
            notFoundContent="В команде нет участников с этой ролью"
          />
          <Button
            type="primary"
            loading={saving}
            disabled={!roleId}
            onClick={() => void addParticipant()}
          >
            {personRoleId ? "Назначить на событие" : "Добавить место"}
          </Button>
        </section>
      )}
      {!event?.role_slots.length && (
        <p className="subtle">На событие пока никто не назначен.</p>
      )}

      {event?.role_slots.map((slot) => {
        const person = members.find((member) =>
          member.roles.some(
            (role) => role.user_ministry_role_id === slot.user_ministry_role_id,
          ),
        );
        const ownRole = members
          .find((member) => member.id === profile.id)
          ?.roles.find((role) => role.id === slot.ministry_role_id);
        const roleName =
          roles.find((role) => role.id === slot.ministry_role_id)?.name ||
          members
            .flatMap((member) => member.roles)
            .find((role) => role.id === slot.ministry_role_id)?.name;
        const roleLabel =
          (roleName || "Роль") +
          (event.role_slots.filter(
            (current) => current.ministry_role_id === slot.ministry_role_id,
          ).length > 1
            ? ` ${slot.slot_number}`
            : "");
        return (
          <div className="event-role" key={slot.id}>
            <div className="event-assignment-grid">
              <div className="event-assignment-role">
                <span>{roleLabel}</span>
                {person ? (
                  <AssignmentStatus status={slot.confirmation_status} />
                ) : (
                  <small>Свободно</small>
                )}
              </div>
              {canAssign ? (
                <Select
                  aria-label={`Назначение: ${roleLabel}`}
                  placeholder="Выберите служителя"
                  allowClear
                  showSearch
                  optionFilterProp="label"
                  className="event-assignment-person"
                  value={slot.user_ministry_role_id ?? undefined}
                  onChange={(value) => void onAssign(slot, value).then(onClose)}
                  options={members.flatMap((member) =>
                    member.roles
                      .filter(
                        (role) =>
                          role.id === slot.ministry_role_id &&
                          roleAllowsEvent(role, event.event_kind || "other"),
                      )
                      .map((role) => ({
                        value: role.user_ministry_role_id,
                        label: `${member.name} ${member.surname}`,
                      })),
                  )}
                />
              ) : (
                <span className="event-assignment-name">
                  {person
                    ? `${person.name} ${person.surname}`
                    : "Пока не назначен"}
                </span>
              )}
            </div>
            {canParticipate &&
              ownRole &&
              (person?.id === profile.id || !person) && (
                <Space>
                  {slot.confirmation_status === "pending" && (
                    <Button
                      size="small"
                      loading={saving}
                      onClick={() => void participation(slot)}
                    >
                      Подтвердить участие
                    </Button>
                  )}
                  {person?.id === profile.id &&
                    slot.confirmation_status !== "replacement" && (
                      <Popconfirm
                        title="Запросить замену?"
                        description="Координатор и админы получат уведомление. До назначения замены вы остаётесь в составе."
                        onConfirm={() => participation(slot, true)}
                        okText="Запросить"
                        cancelText="Отмена"
                      >
                        <Button size="small" danger disabled={saving}>
                          Запросить замену
                        </Button>
                      </Popconfirm>
                    )}
                </Space>
              )}
            {slot.confirmation_status === "replacement" && (
              <p className="subtle">Запрошена замена</p>
            )}
          </div>
        );
      })}
      {canManage && (
        <>
          <h3>Репетиция и напоминания</h3>
          <Form name="event_schedule" form={form} layout="vertical">
            <Form.Item name="rehearsal_at" label="Дата репетиции">
              <DateTimeInput />
            </Form.Item>
            <Form.Item
              name="remindEvent"
              label="Напомнить о служении за сутки и два часа"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item
              name="remindRehearsal"
              label="Напомнить о репетиции за сутки и два часа"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Button
              type="primary"
              loading={saving}
              onClick={() => void saveSchedule()}
            >
              Сохранить настройки
            </Button>
          </Form>
        </>
      )}
      {canManage && (
        <Popconfirm
          title="Удалить событие?"
          description="Будет удалено только это событие со всеми назначениями. Отменить удаление нельзя."
          okText="Удалить"
          cancelText="Отмена"
          onConfirm={deleteEvent}
        >
          <Button
            danger
            loading={saving}
            disabled={demo}
            style={{ marginTop: 32 }}
          >
            Удалить событие
          </Button>
        </Popconfirm>
      )}
    </Drawer>
  );
}
