import MyEvents from "./components/MyEvents";
import { eventsWithMyParticipation } from "./eventFilters";
import AssignmentStatus from "./components/AssignmentStatus";
import { roleAllowsEvent } from "./eventKinds";
import MonthCalendar from "./components/MonthCalendar";
import NotificationPrompt from "./components/NotificationPrompt";
import ChurchDirectory from "./components/ChurchDirectory";
import MembershipApplications from "./components/MembershipApplications";
import type { RegistrationValues } from "./components/RegisterForm";
import EventCreate from "./components/EventCreate";
import type { EventDraft } from "./eventTemplates";
import { disableNotifications, syncNotifications } from "./notifications";
import MinistryRoles from "./components/MinistryRoles";
import MemberRoles from "./components/MemberRoles";
import MemberEventKinds from "./components/MemberEventKinds";
import ThemeSwitcher from "./components/ThemeSwitcher";
import ProfilePage, { type ProfileValues } from "./components/ProfilePage";
import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import EventDetails from "./components/EventDetails";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  DatePicker,
  Empty,
  Select,
  Segmented,
  Space,
  Table,
  Tabs,
  Tag,
  message,
} from "antd";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  LeftOutlined,
  PlusOutlined,
  RightOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import "dayjs/locale/ru";
import Assistant from "./Assistant";
import { api, json } from "./api";
import { accessNames, hasPermission } from "./permissions";
import { demoEvents, demoMembers, demoProfile } from "./demo";
import type { CalendarEvent, Member, Profile, Slot } from "./types";

dayjs.locale("ru");
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "Не удалось выполнить действие";

export default function App() {
  const [demo, setDemo] = useState(
    new URLSearchParams(location.search).has("demo"),
  );
  const [profile, setProfile] = useState<Profile | null>(null);
  const [ministryId, setMinistryId] = useState<number>();
  const [members, setMembers] = useState<Member[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [month, setMonth] = useState(dayjs().startOf("month"));
  const [tab, setTab] = useState(() =>
    location.pathname === "/my-events"
      ? "my-events"
      : location.pathname === "/profile"
        ? "profile"
        : location.pathname === "/members"
          ? "members"
          : location.pathname === "/churches"
            ? "churches"
            : "schedule",
  );
  const navigate = (page: string) => {
    const path =
      page === "my-events"
        ? "/my-events"
        : page === "profile"
          ? "/profile"
          : page === "members"
            ? "/members"
            : page === "churches"
              ? "/churches"
              : "/schedule";
    history.pushState(null, "", path + location.search);
    window.scrollTo(0, 0);
    setTab(page);
  };
  useEffect(() => {
    const onPopState = () =>
      setTab(
        location.pathname === "/my-events"
          ? "my-events"
          : location.pathname === "/profile"
            ? "profile"
            : location.pathname === "/members"
              ? "members"
              : location.pathname === "/churches"
                ? "churches"
                : "schedule",
      );
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const [busy, setBusy] = useState(true);
  const [failure, setFailure] = useState("");
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [personalEvent, setPersonalEvent] = useState<{
    event: CalendarEvent;
    members: Member[];
  } | null>(null);
  const [availabilityRevision, setAvailabilityRevision] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [calendarView, setCalendarView] = useState("calendar");
  const [onlyMyEvents, setOnlyMyEvents] = useState(false);
  const visibleEvents =
    onlyMyEvents && profile
      ? eventsWithMyParticipation(events, members, profile.id)
      : events;
  const [notice, contextHolder] = message.useMessage();
  const ministry = profile?.ministries.find((item) => item.id === ministryId);
  const can = (permission: string) => hasPermission(ministry, permission);
  const detailMinistry = personalEvent
    ? profile?.ministries.find(
        (item) =>
          item.id === (personalEvent.event.church_ministry_id ?? ministryId),
      )
    : ministry;
  const openPersonalEvent = async (eventId: number) => {
    try {
      const event = demo
        ? demoEvents(month.format("YYYY-MM")).find(
            (item) => item.event_id === eventId,
          )!
        : await api<CalendarEvent>(`/portal/events/${eventId}`);
      const people = demo
        ? demoMembers
        : await api<Member[]>(
            `/portal/ministries/${event.church_ministry_id ?? ministryId}/members`,
          );
      setPersonalEvent({ event, members: people });
    } catch (error) {
      notice.error(errorText(error));
    }
  };
  const calendarRequest = useRef(0);
  const demoCreatedEvents = useRef<CalendarEvent[]>([]);
  const loadProfile = async (code?: string) => {
    setBusy(true);
    setFailure("");
    try {
      if (code) await api("/auth/exchange", json("POST", { code }));
      const current = demo ? demoProfile : await api<Profile>("/portal/me");
      setProfile(current);
      if (
        current.ministries.length &&
        (location.pathname === "/" || location.pathname === "/churches")
      ) {
        const initial =
          current.ministries[0].access_level === "member"
            ? "my-events"
            : "schedule";
        history.replaceState(null, "", `/${initial}${location.search}`);
        setTab(initial);
      }
      setMinistryId((previous) =>
        current.ministries.some((item) => item.id === previous)
          ? previous
          : current.ministries[0]?.id,
      );
      if (
        !current.ministries.length &&
        location.pathname !== "/profile" &&
        location.pathname !== "/my-events"
      ) {
        history.replaceState(null, "", "/churches" + location.search);
        setTab("churches");
      }
    } catch (error) {
      if ((error as { status?: number }).status !== 401)
        setFailure(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const code = new URLSearchParams(location.hash.slice(1)).get("code");
    if (code)
      history.replaceState(null, "", location.pathname + location.search);
    void loadProfile(code ?? undefined);
  }, [demo]);
  const passwordLogin = async (login: string, password: string) => {
    setBusy(true);
    setFailure("");
    try {
      await api("/auth/login", json("POST", { login, password }));
      await loadProfile();
    } catch (error) {
      setFailure(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  const register = async (values: RegistrationValues) => {
    setBusy(true);
    setFailure("");
    try {
      await api("/auth/register", json("POST", values));
      await loadProfile();
      navigate("churches");
    } catch (error) {
      setFailure(errorText(error));
    } finally {
      setBusy(false);
    }
  };
  const loadCalendar = async (background = false) => {
    if (!ministryId) return;
    const requestId = ++calendarRequest.current;
    if (!background) {
      setBusy(true);
      setFailure("");
    }
    try {
      if (demo) {
        setEvents([
          ...demoEvents(month.format("YYYY-MM")),
          ...demoCreatedEvents.current.filter((event) =>
            dayjs(event.starts_at).isSame(month, "month"),
          ),
        ]);
        setMembers(demoMembers);
      } else {
        const query = new URLSearchParams({
          start: month.startOf("month").format(),
          end: month.add(1, "month").startOf("month").format(),
        });
        const [calendar, people] = await Promise.all([
          api<CalendarEvent[]>(
            `/portal/ministries/${ministryId}/events?${query}`,
          ),
          api<Member[]>(`/portal/ministries/${ministryId}/members`),
        ]);
        if (requestId === calendarRequest.current) {
          setEvents(calendar);
          setMembers(people);
          setSelected((current) =>
            current
              ? calendar.find((event) => event.event_id === current.event_id) ||
                null
              : null,
          );
        }
      }
    } catch (error) {
      if (!background && requestId === calendarRequest.current)
        setFailure(errorText(error));
    } finally {
      if (requestId === calendarRequest.current) setBusy(false);
    }
  };
  useEffect(() => {
    setEvents([]);
    setMembers([]);
    setSelected(null);
    void loadCalendar();
  }, [ministryId, month.valueOf(), demo]);
  useEffect(() => {
    if (!profile || !ministryId || demo) return;
    const refresh = () => {
      if (!document.hidden) void loadCalendar(true);
    };
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [profile?.id, ministryId, month.valueOf(), demo]);
  useEffect(() => {
    if (!profile || demo) return;
    const sync = () => {
      void syncNotifications().catch(() => {});
    };
    sync();
    window.addEventListener("focus", sync);
    return () => window.removeEventListener("focus", sync);
  }, [profile?.id, demo]);
  const personFor = (id: number | null) =>
    members.find((member) =>
      member.roles.some((role) => role.user_ministry_role_id === id),
    );
  const roles = Array.from(
    new Map(
      members.flatMap((member) =>
        member.roles.map((role) => [role.id, role.name] as const),
      ),
    ).entries(),
  );
  const changeAssignment = async (slot: Slot, value: number | undefined) => {
    if (demo) {
      setEvents((current) =>
        current.map((event) => ({
          ...event,
          role_slots: event.role_slots.map((item) =>
            item.id === slot.id
              ? {
                  ...item,
                  user_ministry_role_id: value ?? null,
                  confirmation_status: "pending",
                }
              : item,
          ),
        })),
      );
      return;
    }
    try {
      await api(
        `/portal/role-slots/${slot.id}`,
        json("PUT", { user_ministry_role_id: value ?? null }),
      );
      await loadCalendar();
    } catch (error) {
      notice.error(errorText(error));
    }
  };
  const logout = async () => {
    try {
      if (!demo) {
        await disableNotifications().catch(() => {});
        await api("/auth/logout", { method: "POST" });
      }
      setProfile(null);
      setDemo(false);
      history.replaceState(null, "", "/");
    } catch (error) {
      notice.error(errorText(error));
    }
  };
  const createEvent = async (payload: EventDraft) => {
    if (demo) {
      const event: CalendarEvent = {
        event_id: Date.now(),
        ...payload,
        song_ids: [],
        role_slots: payload.role_slots.map((slot, index) => ({
          ...slot,
          id: Date.now() + index,
          confirmation_status: "pending",
        })),
        event_reminder_at: payload.reminders_enabled
          ? dayjs(payload.starts_at).subtract(1, "day").format()
          : null,
        rehearsal_reminder_at:
          payload.reminders_enabled && payload.rehearsal_at
            ? dayjs(payload.rehearsal_at).subtract(1, "day").format()
            : null,
      };
      demoCreatedEvents.current.push(event);
      if (dayjs(payload.starts_at).isSame(month, "month"))
        setEvents((current) => [...current, event]);
    } else {
      await api(
        `/portal/ministries/${ministryId}/events`,
        json("POST", payload),
      );
      if (dayjs(payload.starts_at).isSame(month, "month")) await loadCalendar();
    }
    setMonth(dayjs(payload.starts_at).startOf("month"));
    notice.success("Событие добавлено");
  };
  const saveProfile = async (values: ProfileValues) => {
    try {
      if (demo) {
        setProfile((current) => (current ? { ...current, ...values } : null));
        setMembers((current) =>
          current.map((member) =>
            member.id === profile?.id
              ? { ...member, name: values.name, surname: values.surname }
              : member,
          ),
        );
      } else {
        setProfile(await api<Profile>("/portal/me", json("PUT", values)));
      }
      notice.success("Изменения сохранены");
    } catch (error) {
      notice.error(errorText(error));
      throw error;
    }
  };
  const changeAccess = async (member: Member, value: string) => {
    try {
      if (demo)
        setMembers((current) =>
          current.map((item) =>
            item.id === member.id ? { ...item, access_level: value } : item,
          ),
        );
      else {
        await api(
          `/portal/ministries/${ministryId}/members/${member.id}/access`,
          json("PUT", { access_level: value }),
        );
        await loadCalendar();
        setProfile(await api<Profile>("/portal/me"));
      }
      notice.success("Права обновлены");
    } catch (error) {
      notice.error(errorText(error));
    }
  };
  if (!profile)
    return (
      <Login
        busy={busy}
        failure={failure}
        onLogin={(code) => void loadProfile(code)}
        onPasswordLogin={passwordLogin}
        onRegister={register}
        onDemo={() => setDemo(true)}
      />
    );

  return (
    <div className="app-shell">
      {contextHolder}
      <Sidebar
        profile={profile}
        ministry={ministry}
        tab={tab}
        eventCount={events.length}
        memberCount={members.length}
        onTab={navigate}
        onProfile={() => navigate("profile")}
        onLogout={() => void logout()}
      />
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Слово жизни <span>/</span>{" "}
            {tab === "my-events"
              ? "Доступность"
              : tab === "profile"
                ? "Моя карточка"
                : tab === "churches" || !ministry
                  ? "Церкви и команды"
                  : ministry.name}
          </div>
          <Space>
            <ThemeSwitcher />
            <Button onClick={() => void logout()}>Выйти</Button>
            <span className="live-dot" />{" "}
            <span className="topbar-caption">Рабочее пространство</span>
            <button
              className="header-profile-button"
              aria-label="Настройки аккаунта"
              title="Настройки аккаунта"
              onClick={() => navigate("profile")}
            >
              <Avatar size="small" className="header-avatar">
                {profile.name[0]}
              </Avatar>
            </button>
          </Space>
        </header>
        <main className="workspace-content">
          {demo && (
            <Alert
              className="demo-banner"
              type="info"
              message="Демонстрация · данные примера. Изменения не сохраняются на сервере."
              action={
                <Button
                  size="small"
                  onClick={() => {
                    setDemo(false);
                    setProfile(null);
                  }}
                >
                  Войти
                </Button>
              }
            />
          )}
          {!demo && <NotificationPrompt userId={profile.id} />}
          {tab === "churches" ||
          (!ministry && tab !== "profile" && tab !== "my-events") ? (
            <ChurchDirectory
              demo={demo}
              onRefreshProfile={() => loadProfile()}
            />
          ) : tab === "my-events" ? (
            <MyEvents
              key={availabilityRevision}
              demo={demo}
              onChanged={() => void loadCalendar()}
              onOpen={(eventId) => void openPersonalEvent(eventId)}
            />
          ) : tab === "profile" ? (
            <>
              <ProfilePage
                demo={demo}
                profile={profile}
                members={members}
                onSave={saveProfile}
                onBack={() => navigate("schedule")}
              />
              <Button onClick={() => navigate("churches")}>
                Церкви и команды · вступить в другую команду
              </Button>
            </>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">ПРОСТРАНСТВО СЛУЖЕНИЯ</span>
                  <h1>
                    {tab === "schedule"
                      ? "Расписание служения"
                      : "Участники служения"}
                  </h1>
                  <p>
                    {tab === "schedule"
                      ? "События, состав команды и назначения на месяц."
                      : "Состав команды, роли и доступ к служению."}
                  </p>
                </div>
                <Select
                  className="ministry-select"
                  aria-label="Выберите служение"
                  value={ministryId}
                  options={profile.ministries.map((item) => ({
                    value: item.id,
                    label: item.name,
                  }))}
                  onChange={setMinistryId}
                />
              </div>
              {ministry && (
                <>
                  <div className="summary-strip">
                    <div>
                      <span className="stat-icon lavender">
                        <CalendarOutlined />
                      </span>
                      <div>
                        <strong>{events.length}</strong>
                        <span>событий в этом месяце</span>
                      </div>
                    </div>
                    <div>
                      <span className="stat-icon sage">
                        <TeamOutlined />
                      </span>
                      <div>
                        <strong>{members.length}</strong>
                        <span>участников в команде</span>
                      </div>
                    </div>
                    <div>
                      <span className="stat-icon sand">
                        <CheckCircleOutlined />
                      </span>
                      <div>
                        <strong>
                          {events.reduce(
                            (total, event) =>
                              total +
                              event.role_slots.filter(
                                (slot) => slot.user_ministry_role_id === null,
                              ).length,
                            0,
                          )}
                        </strong>
                        <span>мест ждут участника</span>
                      </div>
                    </div>
                  </div>
                  {failure && (
                    <Alert
                      type="error"
                      showIcon
                      message={failure}
                      action={
                        <Button onClick={() => void loadCalendar()}>
                          Повторить
                        </Button>
                      }
                    />
                  )}
                  <div
                    className={`content-grid ${can("use_assistant") && tab === "schedule" ? "with-assistant" : ""}`}
                  >
                    <section className="panel schedule-panel">
                      <div className="panel-toolbar">
                        <div>
                          <h2>
                            {tab === "schedule"
                              ? "Расписание служения"
                              : "Наша команда"}
                          </h2>
                          <span className="subtle">
                            {ministry.name} <span className="separator">·</span>{" "}
                            {accessNames[ministry.access_level]}
                          </span>
                        </div>
                        {can("manage_events") && (
                          <Button
                            type="primary"
                            icon={<PlusOutlined />}
                            onClick={() => setShowCreate(true)}
                          >
                            Событие
                          </Button>
                        )}
                      </div>
                      <div className="calendar-toolbar">
                        <Tabs
                          activeKey={tab}
                          onChange={navigate}
                          items={[
                            { key: "schedule", label: "Расписание" },
                            { key: "members", label: "Участники" },
                          ]}
                        />
                        <Space size={4}>
                          <Button
                            type="text"
                            icon={<LeftOutlined />}
                            aria-label="Предыдущий месяц"
                            onClick={() => setMonth(month.subtract(1, "month"))}
                          />
                          <DatePicker
                            picker="month"
                            allowClear={false}
                            value={month}
                            format="MMMM YYYY"
                            onChange={(value) =>
                              value && setMonth(value.startOf("month"))
                            }
                          />
                          <Button
                            type="text"
                            icon={<RightOutlined />}
                            aria-label="Следующий месяц"
                            onClick={() => setMonth(month.add(1, "month"))}
                          />
                        </Space>
                      </div>
                      {tab === "schedule" ? (
                        <>
                          <div className="calendar-options">
                            <Segmented
                              className="calendar-view-switch"
                              value={calendarView}
                              onChange={setCalendarView}
                              options={[
                                { value: "calendar", label: "Календарь" },
                                { value: "table", label: "Таблица состава" },
                              ]}
                            />
                            <Segmented
                              aria-label="Фильтр событий"
                              value={onlyMyEvents ? "mine" : "all"}
                              onChange={(value) =>
                                setOnlyMyEvents(value === "mine")
                              }
                              options={[
                                { value: "all", label: "Все события" },
                                {
                                  value: "mine",
                                  label: "Только с моим участием",
                                },
                              ]}
                            />
                          </div>
                          {onlyMyEvents &&
                            !busy &&
                            visibleEvents.length === 0 && (
                              <Alert
                                type="info"
                                showIcon
                                style={{ margin: "0 16px 16px" }}
                                message="В этом месяце у вас пока нет назначений"
                                action={
                                  <Button
                                    size="small"
                                    onClick={() => setOnlyMyEvents(false)}
                                  >
                                    Все события
                                  </Button>
                                }
                              />
                            )}
                          {calendarView === "calendar" ? (
                            <MonthCalendar
                              month={month}
                              events={visibleEvents}
                              busy={busy}
                              onEvent={setSelected}
                            />
                          ) : (
                            <Table<CalendarEvent>
                              rowKey="event_id"
                              loading={busy}
                              dataSource={visibleEvents}
                              pagination={false}
                              scroll={{ x: 620 }}
                              locale={{
                                emptyText: (
                                  <Empty description="В этом месяце пока нет событий" />
                                ),
                              }}
                              columns={[
                                {
                                  title: "Событие",
                                  key: "date",
                                  width: 205,
                                  fixed: "left",
                                  render: (
                                    value: unknown,
                                    event: CalendarEvent,
                                  ) => (
                                    <button
                                      className="event-cell"
                                      onClick={() => setSelected(event)}
                                    >
                                      <span className="event-date">
                                        <b>
                                          {dayjs(event.starts_at).format("DD")}
                                        </b>
                                        <small>
                                          {dayjs(event.starts_at).format("dd")}
                                        </small>
                                      </span>
                                      <span>
                                        <strong>{event.event_name}</strong>
                                        <small>
                                          {dayjs(event.starts_at).format(
                                            "HH:mm",
                                          )}{" "}
                                          · Основное служение
                                        </small>
                                        {can("manage_assignments") && (
                                          <small>Состав и назначения →</small>
                                        )}
                                      </span>
                                    </button>
                                  ),
                                },
                                ...roles.map(([roleId, roleName]) => ({
                                  title: roleName,
                                  key: String(roleId),
                                  width: 155,
                                  render: (
                                    value: unknown,
                                    event: CalendarEvent,
                                  ) => {
                                    const slots = event.role_slots.filter(
                                      (slot) =>
                                        slot.ministry_role_id === roleId,
                                    );
                                    return slots.length ? (
                                      slots.map((slot) => {
                                        const person = personFor(
                                          slot.user_ministry_role_id,
                                        );
                                        return can("manage_assignments") ? (
                                          <div
                                            key={slot.id}
                                            className="assignment-editor"
                                          >
                                            <Select
                                              key={slot.id}
                                              className={`assignment-select ${person ? "" : "unfilled"}`}
                                              aria-label={`${roleName}, ${dayjs(event.starts_at).format("DD MMM")}`}
                                              allowClear
                                              value={
                                                slot.user_ministry_role_id ??
                                                undefined
                                              }
                                              placeholder="Нужен участник"
                                              options={members.flatMap(
                                                (member) =>
                                                  member.roles
                                                    .filter(
                                                      (role) =>
                                                        role.id === roleId &&
                                                        roleAllowsEvent(
                                                          role,
                                                          event.event_kind ||
                                                            "other",
                                                        ),
                                                    )
                                                    .map((role) => ({
                                                      value:
                                                        role.user_ministry_role_id,
                                                      label:
                                                        member.name +
                                                        " " +
                                                        member.surname,
                                                    })),
                                              )}
                                              onChange={(value) =>
                                                void changeAssignment(
                                                  slot,
                                                  value,
                                                )
                                              }
                                            />
                                            {person && (
                                              <AssignmentStatus
                                                status={
                                                  slot.confirmation_status
                                                }
                                              />
                                            )}
                                          </div>
                                        ) : (
                                          <div
                                            className="assignment"
                                            key={slot.id}
                                          >
                                            {person ? (
                                              <>
                                                <span
                                                  className={`status-dot ${slot.confirmation_status === "confirmed" ? "confirmed" : ""}`}
                                                />
                                                {person.name} {person.surname}
                                              </>
                                            ) : (
                                              <span className="open-slot">
                                                Нужен участник
                                              </span>
                                            )}
                                          </div>
                                        );
                                      })
                                    ) : (
                                      <span className="subtle">—</span>
                                    );
                                  },
                                })),
                              ]}
                            />
                          )}
                        </>
                      ) : (
                        <div>
                          {!demo && ministryId && can("manage_members") && (
                            <MembershipApplications
                              ministryId={ministryId}
                              onChanged={() => void loadCalendar()}
                            />
                          )}
                          {!demo && ministryId && can("manage_members") && (
                            <div style={{ padding: "16px 20px" }}>
                              <MinistryRoles
                                ministryId={ministryId}
                                onChanged={() => void loadCalendar()}
                              />
                            </div>
                          )}
                          <Table<Member>
                            rowKey="id"
                            loading={busy}
                            dataSource={members}
                            pagination={false}
                            scroll={{ x: 500 }}
                            columns={[
                              {
                                title: "Служитель",
                                key: "name",
                                render: (value: unknown, person: Member) => (
                                  <Space>
                                    <Avatar className="member-avatar">
                                      {person.name[0]}
                                    </Avatar>
                                    <strong>
                                      {person.name} {person.surname}
                                      {person.id === profile.id && (
                                        <span className="subtle"> · вы</span>
                                      )}
                                    </strong>
                                  </Space>
                                ),
                              },
                              {
                                title: "Роли",
                                key: "roles",
                                render: (value: unknown, person: Member) => (
                                  <Space wrap>
                                    {person.roles.map((role) => (
                                      <Tag key={role.id}>{role.name}</Tag>
                                    ))}
                                    {!demo &&
                                      ministryId &&
                                      can("manage_assignments") && (
                                        <MemberRoles
                                          ministryId={ministryId}
                                          member={person}
                                          onChanged={() => void loadCalendar()}
                                        />
                                      )}
                                    {!demo &&
                                      ministryId &&
                                      can("manage_assignments") && (
                                        <MemberEventKinds
                                          member={person}
                                          ministryId={ministryId}
                                          onChanged={() => void loadCalendar()}
                                        />
                                      )}
                                  </Space>
                                ),
                              },
                              {
                                title: "Уведомления",
                                key: "notifications",
                                render: (value: unknown, person: Member) => (
                                  <Tag
                                    title={
                                      person.notifications_checked_at
                                        ? `Последняя проверка: ${dayjs(person.notifications_checked_at).format("DD.MM.YYYY HH:mm")}. Настройки телефона сайт не видит.`
                                        : "Служителю нужно включить уведомления в своей карточке"
                                    }
                                    color={
                                      person.notification_status === "enabled"
                                        ? "success"
                                        : "warning"
                                    }
                                  >
                                    {person.notification_status === "enabled"
                                      ? "Подключены"
                                      : person.notification_status ===
                                          "needs_check"
                                        ? "Нужно проверить"
                                        : "Нужно включить"}
                                  </Tag>
                                ),
                              },
                              {
                                title: "Доступ",
                                key: "access",
                                render: (value: unknown, person: Member) =>
                                  can("manage_members") ? (
                                    <Select
                                      value={person.access_level}
                                      style={{ width: 155 }}
                                      options={[
                                        "member",
                                        "coordinator",
                                        "admin",
                                      ].map((value) => ({
                                        value,
                                        label: accessNames[value],
                                      }))}
                                      onChange={(value) =>
                                        void changeAccess(person, value)
                                      }
                                    />
                                  ) : (
                                    <Tag>
                                      {accessNames[person.access_level]}
                                    </Tag>
                                  ),
                              },
                            ]}
                          />
                        </div>
                      )}
                      <div className="table-footer">
                        <span>
                          <span className="status-dot confirmed" /> Подтверждено
                        </span>
                        <span>
                          <span className="status-dot" /> Ожидает подтверждения
                        </span>
                        <small>
                          Нажмите на событие, чтобы увидеть подробности
                        </small>
                      </div>
                    </section>
                    {can("use_assistant") && tab === "schedule" && (
                      <Assistant
                        key={`${ministryId}-${month.format("YYYY-MM")}`}
                        ministryId={ministry.id}
                        month={month.format("YYYY-MM")}
                        demo={demo}
                        members={members}
                        onApplied={() => void loadCalendar()}
                      />
                    )}
                  </div>
                  <footer className="page-footer">
                    Слово жизни <span>Пространство служения</span>
                  </footer>
                </>
              )}
            </>
          )}
        </main>
      </div>
      {ministryId && (
        <EventCreate
          open={showCreate}
          ministryId={ministryId}
          demo={demo}
          canManageTemplates={can("manage_members")}
          members={members}
          onClose={() => setShowCreate(false)}
          onCreate={createEvent}
        />
      )}
      <EventDetails
        event={personalEvent?.event ?? selected}
        members={personalEvent?.members ?? members}
        profile={profile}
        canManage={hasPermission(detailMinistry, "manage_events")}
        canAssign={hasPermission(detailMinistry, "manage_assignments")}
        ministryId={detailMinistry?.id}
        onAssign={changeAssignment}
        canParticipate={hasPermission(detailMinistry, "self_signup")}
        demo={demo}
        onClose={() => {
          setSelected(null);
          setPersonalEvent(null);
        }}
        onSaved={() => {
          void loadCalendar();
          setAvailabilityRevision((value) => value + 1);
        }}
      />
    </div>
  );
}
