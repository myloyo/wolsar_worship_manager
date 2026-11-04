import ChurchLogo from "./ChurchLogo";
import { Avatar, Button } from "antd";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  GlobalOutlined,
  TeamOutlined,
  UserOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import type { Profile, Ministry } from "../types";
import { accessNames } from "../permissions";

type Props = {
  profile: Profile;
  ministry: Ministry | undefined;
  tab: string;
  eventCount: number;
  memberCount: number;
  onTab: (tab: string) => void;
  onProfile: () => void;
  onLogout: () => void;
};
export default function Sidebar({
  profile,
  ministry,
  tab,
  eventCount,
  memberCount,
  onTab,
  onProfile,
  onLogout,
}: Props) {
  return (
    <aside className="sidebar">
      <a
        className="brand"
        href={`/schedule${location.search}`}
        onClick={(event) => {
          event.preventDefault();
          onTab("schedule");
        }}
      >
        <ChurchLogo />
      </a>
      <div className="church-label">
        <strong>{ministry?.church_name || "Личный кабинет"}</strong>
        <span className="church-description">Служение и команда</span>
      </div>
      <nav aria-label="Разделы">
        <button
          className={tab === "my-events" ? "active" : ""}
          onClick={() => onTab("my-events")}
        >
          <CheckCircleOutlined /> Доступность
        </button>
        {(!ministry || ministry.access_level !== "member") && (
          <button
            className={tab === "churches" ? "active" : ""}
            onClick={() => onTab("churches")}
          >
            <GlobalOutlined /> Церкви и команды
          </button>
        )}
        <button
          className={tab === "schedule" ? "active" : ""}
          onClick={() => onTab("schedule")}
        >
          <CalendarOutlined /> Расписание{" "}
          <span className="nav-count">{eventCount}</span>
        </button>
        <button
          className={tab === "members" ? "active" : ""}
          onClick={() => onTab("members")}
        >
          <TeamOutlined /> Участники{" "}
          <span className="nav-count">{memberCount}</span>
        </button>
        {ministry?.access_level !== "member" && (
          <button
            className={tab === "profile" ? "active" : ""}
            onClick={onProfile}
          >
            <UserOutlined /> Моя карточка
          </button>
        )}
      </nav>
      <div className="sidebar-note">
        <span className="sidebar-section-label">РАБОЧЕЕ ПРОСТРАНСТВО</span>
        <p>
          Всё для служения.
          <br />В одной команде.
        </p>
        <small>Слово жизни</small>
      </div>
      <button className="user-menu" onClick={onProfile}>
        <Avatar className="user-avatar">
          {profile.name[0]}
          {profile.surname[0]}
        </Avatar>
        <span>
          <strong>
            {profile.name} {profile.surname}
          </strong>
          <small>{accessNames[ministry?.access_level ?? "member"]}</small>
        </span>
      </button>
      <Button
        type="text"
        size="small"
        icon={<LogoutOutlined />}
        onClick={onLogout}
      >
        Выйти
      </Button>
    </aside>
  );
}
