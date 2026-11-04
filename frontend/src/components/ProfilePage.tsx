import TelegramConnection from "./TelegramConnection";
import LoginSettings from "./LoginSettings";
import NotificationSettings from "./NotificationSettings";
import { useEffect, useState } from "react";
import { Avatar, Button, DatePicker, Form, Input, Tag } from "antd";
import {
  ArrowLeftOutlined,
  CheckOutlined,
  UserOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import type { Profile, Member } from "../types";
import { accessNames } from "../permissions";

export type ProfileValues = {
  name: string;
  surname: string;
  birthday_date: string | null;
};
type Props = {
  demo: boolean;
  profile: Profile;
  members: Member[];
  onSave: (values: ProfileValues) => Promise<void>;
  onBack: () => void;
};

export default function ProfilePage({
  profile,
  demo,
  members,
  onSave,
  onBack,
}: Props) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const ownRoles =
    members.find((member) => member.id === profile.id)?.roles ?? [];
  useEffect(() => {
    form.setFieldsValue({
      ...profile,
      birthday_date: profile.birthday_date
        ? dayjs(profile.birthday_date)
        : null,
    });
  }, [profile, form]);
  const submit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await onSave({
        name: values.name.trim(),
        surname: values.surname.trim(),
        birthday_date: values.birthday_date?.format("YYYY-MM-DD") ?? null,
      });
    } catch {
      /* The form and parent report validation and request errors. */
    } finally {
      setSaving(false);
    }
  };
  return (
    <section className="profile-page">
      <button className="back-link" onClick={onBack}>
        <ArrowLeftOutlined /> К расписанию
      </button>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ЛИЧНЫЙ ПРОФИЛЬ</span>
          <h1>Моя карточка</h1>
          <p>Ваши данные и участие в служениях.</p>
        </div>
        <Button
          type="primary"
          icon={<CheckOutlined />}
          loading={saving}
          onClick={() => void submit()}
        >
          Сохранить изменения
        </Button>
      </div>
      <div className="profile-layout">
        <aside className="profile-identity panel">
          <div className="profile-cover">
            <span className="profile-cover-label">СЛОВО ЖИЗНИ</span>
            <span className="profile-cover-cross">✳</span>
          </div>
          <Avatar size={88} className="profile-avatar" icon={<UserOutlined />}>
            {profile.name[0]}
            {profile.surname[0]}
          </Avatar>
          <h2>
            {profile.name}
            <br />
            {profile.surname}
          </h2>
          <span className="subtle">Служитель церкви</span>
          <div className="profile-role-list">
            {ownRoles.map((role) => (
              <Tag key={role.id}>{role.name}</Tag>
            ))}
          </div>
          <div className="profile-identity-note">
            <CheckOutlined /> Карточка участника{" "}
            <span>№ {String(profile.id).padStart(4, "0")}</span>
          </div>
        </aside>
        <div className="profile-main">
          <LoginSettings demo={demo} />
          <TelegramConnection demo={demo} />
          <NotificationSettings demo={demo} />
          <section className="panel profile-form-panel">
            <div className="section-heading">
              <h2>Личные данные</h2>
              <p>Эта информация отображается в вашем профиле.</p>
            </div>
            <Form form={form} layout="vertical" requiredMark={false}>
              <div className="profile-form-grid">
                <Form.Item
                  name="name"
                  label="Имя"
                  rules={[
                    {
                      required: true,
                      whitespace: true,
                      message: "Укажите имя",
                    },
                  ]}
                >
                  <Input maxLength={100} size="large" />
                </Form.Item>
                <Form.Item
                  name="surname"
                  label="Фамилия"
                  rules={[
                    {
                      required: true,
                      whitespace: true,
                      message: "Укажите фамилию",
                    },
                  ]}
                >
                  <Input maxLength={100} size="large" />
                </Form.Item>
                <Form.Item name="birthday_date" label="Дата рождения">
                  <DatePicker
                    format="DD.MM.YYYY"
                    placeholder="Выберите дату"
                    disabledDate={(date) => date.isAfter(dayjs(), "day")}
                    size="large"
                  />
                </Form.Item>
              </div>
            </Form>
          </section>
          <section className="panel profile-ministries">
            <div className="section-heading">
              <h2>Мои служения</h2>
              <p>Команды, частью которых вы являетесь.</p>
            </div>
            {profile.ministries.length ? (
              profile.ministries.map((ministry) => (
                <div className="profile-ministry" key={ministry.id}>
                  <span className="ministry-monogram">{ministry.name[0]}</span>
                  <div>
                    <strong>{ministry.name}</strong>
                    <small>{ministry.church_name}</small>
                  </div>
                  <Tag>
                    {accessNames[ministry.access_level] ??
                      ministry.access_level}
                  </Tag>
                </div>
              ))
            ) : (
              <p className="subtle">Вы пока не состоите в служении.</p>
            )}
          </section>
        </div>
      </div>
    </section>
  );
}
