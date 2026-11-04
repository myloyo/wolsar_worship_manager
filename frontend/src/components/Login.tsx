import RegisterForm, { type RegistrationValues } from "./RegisterForm";
import ThemeSwitcher from "./ThemeSwitcher";
import ChurchLogo from "./ChurchLogo";
import { useState } from "react";
import { Alert, Button, Card, Form, Input, Segmented } from "antd";

type Props = {
  busy: boolean;
  failure: string;
  onLogin: (code: string) => void;
  onPasswordLogin: (login: string, password: string) => Promise<void>;
  onDemo: () => void;
  onRegister: (values: RegistrationValues) => Promise<void>;
};
export default function Login({
  busy,
  failure,
  onLogin,
  onPasswordLogin,
  onRegister,
  onDemo,
}: Props) {
  const [code, setCode] = useState("");
  const [mode, setMode] = useState("password");
  return (
    <main className="login-page">
      <div className="login-theme">
        <ThemeSwitcher />
      </div>
      <div className="login-art">
        <ChurchLogo />
        <span className="eyebrow">ПРОСТРАНСТВО СЛУЖЕНИЯ</span>
        <h1>
          Ваше служение.
          <br />
          Ваша команда.
        </h1>
        <p>Расписание, люди и задачи — в одном рабочем пространстве.</p>
        <div className="login-workspace-preview">
          <span>ПРОСЛАВЛЕНИЕ</span>
          <strong>Воскресное служение</strong>
          <div>
            <b>11:00</b>
            <span>Команда собрана</span>
          </div>
          <div className="preview-people">
            <i>АС</i>
            <i>МО</i>
            <i>СВ</i>
            <i>+2</i>
          </div>
        </div>
        <small>СЛОВО ЖИЗНИ · ПРОСТРАНСТВО СЛУЖЕНИЯ</small>
      </div>
      <Card className="login-card">
        <span className="eyebrow">ДОБРО ПОЖАЛОВАТЬ</span>
        <h2>
          {mode === "register"
            ? "Личный аккаунт"
            : "Вход в рабочее пространство"}
        </h2>
        <Segmented
          block
          value={mode}
          onChange={setMode}
          options={[
            { label: "Вход", value: "password" },
            { label: "Регистрация", value: "register" },
            { label: "Через Telegram", value: "telegram" },
          ]}
        />
        {failure && (
          <Alert
            type="error"
            message={failure}
            showIcon
            style={{ marginTop: 16 }}
          />
        )}
        {mode === "register" ? (
          <RegisterForm busy={busy} onRegister={onRegister} />
        ) : mode === "password" ? (
          <>
            <p>
              Войдите с логином и паролем, которые вы настроили в личной
              карточке.
            </p>
            <Form
              name="password_login"
              layout="vertical"
              onFinish={(values) =>
                void onPasswordLogin(values.login, values.password)
              }
            >
              <Form.Item
                name="login"
                label="Логин"
                rules={[
                  {
                    required: true,
                    whitespace: true,
                    message: "Введите логин",
                  },
                ]}
              >
                <Input autoComplete="username" maxLength={64} />
              </Form.Item>
              <Form.Item
                name="password"
                label="Пароль"
                rules={[{ required: true, message: "Введите пароль" }]}
              >
                <Input.Password
                  autoComplete="current-password"
                  maxLength={128}
                />
              </Form.Item>
              <Button block type="primary" htmlType="submit" loading={busy}>
                Войти
              </Button>
            </Form>
            <p>
              Ещё не настроили пароль? Войдите через привязанный Telegram или
              получите ссылку у администратора сервера, затем откройте «Моя
              карточка → Вход в аккаунт».
            </p>
          </>
        ) : (
          <>
            <p>
              Откройте нашего Telegram-бота{" "}
              <a
                href="https://t.me/wolsar_worship_bot"
                target="_blank"
                rel="noreferrer"
              >
                @wolsar_worship_bot
              </a>
              . Он помогает смотреть расписание и получать напоминания о
              служении.
            </p>
            <p>
              Если Telegram уже привязан, отправьте боту <b>/login</b> и
              откройте полученную ссылку. Привязать Telegram можно после входа
              на сайт в разделе «Моя карточка». Новый аккаунт создаётся во
              вкладке «Регистрация».
            </p>
            <Form layout="vertical" onFinish={() => onLogin(code.trim())}>
              <Form.Item label="Или вставьте код из ссылки">
                <Input
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  autoComplete="off"
                  placeholder="Код входа"
                />
              </Form.Item>
              <Button
                type="primary"
                block
                htmlType="submit"
                loading={busy}
                disabled={!code.trim()}
              >
                Войти в пространство
              </Button>
            </Form>
          </>
        )}
        <Button type="link" block onClick={onDemo}>
          Посмотреть пример интерфейса ↗
        </Button>
        {mode === "telegram" && (
          <small>Ссылка действует 5 минут и используется один раз.</small>
        )}
      </Card>
    </main>
  );
}
