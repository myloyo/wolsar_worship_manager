import { useEffect, useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import { api, json } from "../api";

type Credentials = { login: string | null; has_password: boolean };
type Values = {
  login: string;
  password: string;
  current_password?: string;
  repeat_password: string;
};
export default function LoginSettings({ demo }: { demo: boolean }) {
  const [form] = Form.useForm<Values>();
  const [credentials, setCredentials] = useState<Credentials>({
    login: null,
    has_password: false,
  });
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(demo);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (demo) return;
    let active = true;
    api<Credentials>("/auth/credentials")
      .then((value) => {
        if (active) {
          setCredentials(value);
          form.setFieldsValue({ login: value.login || "" });
          setLoaded(true);
        }
      })
      .catch((error) => {
        if (active)
          setError(
            error instanceof Error
              ? error.message
              : "Не удалось загрузить настройки входа",
          );
      });
    return () => {
      active = false;
    };
  }, [demo, form]);
  const save = async (values: Values) => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const current = await api<Credentials>(
        "/auth/credentials",
        json("PUT", {
          login: values.login,
          password: values.password,
          current_password: values.current_password || null,
        }),
      );
      setCredentials(current);
      form.resetFields(["password", "repeat_password", "current_password"]);
      setSaved(true);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось сохранить способ входа",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel profile-form-panel">
      <div className="section-heading">
        <h2>Вход в аккаунт</h2>
        <p>
          Задайте логин и пароль, чтобы заходить на сайт без Telegram. Ваша
          карточка и права сохранятся.
        </p>
      </div>
      {demo && (
        <Alert
          type="info"
          message="Настройка доступна после входа в свой аккаунт."
        />
      )}
      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 16 }} />
      )}
      {saved && (
        <Alert
          type="success"
          message="Сохранено. Теперь вы можете входить по логину и паролю."
          style={{ marginBottom: 16 }}
        />
      )}
      <Form
        name="login_settings"
        form={form}
        layout="vertical"
        disabled={demo || !loaded || busy}
        onFinish={(values) => void save(values)}
      >
        <Form.Item
          name="login"
          label="Логин"
          extra="3–64 символа: латинские буквы, цифры, точка, дефис или подчёркивание."
          rules={[
            {
              required: true,
              pattern: /^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$/,
              message: "Проверьте формат логина",
            },
          ]}
        >
          <Input
            autoComplete="username"
            maxLength={64}
            placeholder="Например, nastya"
          />
        </Form.Item>
        {credentials.has_password && (
          <Form.Item
            name="current_password"
            label="Текущий пароль"
            rules={[{ required: true, message: "Введите текущий пароль" }]}
          >
            <Input.Password autoComplete="current-password" maxLength={128} />
          </Form.Item>
        )}
        <Form.Item
          name="password"
          label={credentials.has_password ? "Новый пароль" : "Пароль"}
          rules={[
            {
              required: true,
              min: 10,
              max: 128,
              message: "От 10 до 128 символов",
            },
          ]}
        >
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Form.Item
          name="repeat_password"
          label="Повторите пароль"
          dependencies={["password"]}
          rules={[
            { required: true, message: "Повторите пароль" },
            ({ getFieldValue }) => ({
              validator: async (valueRule, value) => {
                if (value !== getFieldValue("password"))
                  throw new Error("Пароли не совпадают");
              },
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={busy}>
          Сохранить способ входа
        </Button>
      </Form>
    </section>
  );
}
