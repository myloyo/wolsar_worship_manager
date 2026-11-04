import { Button, Checkbox, Form, Input } from "antd";
export type RegistrationValues = {
  name: string;
  surname: string;
  login: string;
  password: string;
  consent_approved: boolean;
};
export default function RegisterForm({
  busy,
  onRegister,
}: {
  busy: boolean;
  onRegister: (values: RegistrationValues) => Promise<void>;
}) {
  return (
    <>
      <p>
        Создайте личный аккаунт. Церковь и команду выберете после регистрации.
      </p>
      <Form
        name="site_registration"
        layout="vertical"
        onFinish={(values) =>
          void onRegister({
            name: values.name,
            surname: values.surname,
            login: values.login,
            password: values.password,
            consent_approved: values.consent_approved,
          })
        }
      >
        <Form.Item
          name="name"
          label="Имя"
          rules={[{ required: true, whitespace: true, message: "Укажите имя" }]}
        >
          <Input autoComplete="given-name" maxLength={100} />
        </Form.Item>
        <Form.Item
          name="surname"
          label="Фамилия"
          rules={[
            { required: true, whitespace: true, message: "Укажите фамилию" },
          ]}
        >
          <Input autoComplete="family-name" maxLength={100} />
        </Form.Item>
        <Form.Item
          name="login"
          label="Логин"
          extra="Латинские буквы, цифры, точка, дефис или подчёркивание."
          rules={[
            {
              required: true,
              pattern: /^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$/,
              message: "От 3 до 64 латинских символов",
            },
          ]}
        >
          <Input autoComplete="username" maxLength={64} />
        </Form.Item>
        <Form.Item
          name="password"
          label="Пароль"
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
              validator: async (rule, value) => {
                if (value !== getFieldValue("password"))
                  throw new Error("Пароли не совпадают");
              },
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Form.Item
          name="consent_approved"
          valuePropName="checked"
          rules={[
            {
              validator: async (rule, value) => {
                if (!value)
                  throw new Error("Нужно согласие на обработку данных");
              },
            },
          ]}
        >
          <Checkbox>
            Согласен на обработку имени, фамилии и данных об участии для работы
            сервиса
          </Checkbox>
        </Form.Item>
        <Button type="primary" block htmlType="submit" loading={busy}>
          Создать аккаунт
        </Button>
      </Form>
    </>
  );
}
