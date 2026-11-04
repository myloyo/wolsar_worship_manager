import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Tag,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { api, json } from "../api";

type Team = {
  id: number;
  name: string;
  status: string;
  decision_note: string | null;
  roles: { id: number; name: string }[];
};
type Church = { id: number; name: string; teams: Team[] };
export default function ChurchDirectory({
  demo,
  onRefreshProfile,
}: {
  demo: boolean;
  onRefreshProfile: () => Promise<void>;
}) {
  const [churches, setChurches] = useState<Church[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Team | null>(null);
  const [form] = Form.useForm();
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      setChurches(
        demo
          ? [
              {
                id: 1,
                name: "Церковь «Слово жизни»",
                teams: [
                  {
                    id: 1,
                    name: "Прославление",
                    status: "member",
                    decision_note: null,
                    roles: [],
                  },
                ],
              },
            ]
          : await api<Church[]>("/portal/directory"),
      );
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось загрузить каталог",
      );
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    void load();
  }, [demo]);
  const apply = async () => {
    if (!selected) return;
    const values = await form.validateFields();
    setBusy(true);
    setError("");
    try {
      await api(
        `/portal/ministries/${selected.id}/applications`,
        json("POST", {
          role_ids: values.role_ids || [],
          message: values.message || null,
        }),
      );
      setSelected(null);
      form.resetFields();
      await load();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось отправить заявку",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section>
      <div className="page-heading">
        <div>
          <span className="eyebrow">НАЙДИТЕ СВОЮ КОМАНДУ</span>
          <h1>Церкви и команды</h1>
          <p>
            Выберите служение и подайте заявку. Доступ к команде откроется после
            одобрения администратора.
          </p>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={busy}
          onClick={() =>
            void (async () => {
              await load();
              await onRefreshProfile();
            })()
          }
        >
          Обновить
        </Button>
      </div>
      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 20 }} />
      )}
      {!busy && !churches.length && (
        <Empty description="Пока нет зарегистрированных церквей и команд" />
      )}
      <div className="directory-grid">
        {churches.map((church) => (
          <section className="panel directory-church" key={church.id}>
            <h2>{church.name}</h2>
            {!church.teams.length && (
              <p className="subtle">Команды пока не добавлены.</p>
            )}
            {church.teams.map((team) => (
              <div className="directory-team" key={team.id}>
                <div>
                  <strong>{team.name}</strong>
                  <p className="subtle">
                    {team.roles.map((role) => role.name).join(" · ") ||
                      "Команда служения"}
                  </p>
                </div>
                {team.status === "member" ? (
                  <Tag color="success">Вы в команде</Tag>
                ) : team.status === "pending" ? (
                  <Tag color="processing">Заявка на рассмотрении</Tag>
                ) : (
                  <Button
                    disabled={demo}
                    onClick={() => {
                      form.resetFields();
                      setSelected(team);
                    }}
                  >
                    {" "}
                    {team.status === "rejected"
                      ? "Подать повторно"
                      : "Подать заявку"}
                  </Button>
                )}
                {team.status === "rejected" && (
                  <p className="subtle">
                    {team.decision_note ||
                      "Заявка не одобрена. Можно уточнить данные и подать её повторно."}
                  </p>
                )}
              </div>
            ))}
          </section>
        ))}
      </div>
      <Modal
        title={`Заявка в служение «${selected?.name || ""}»`}
        open={!!selected}
        onCancel={() => setSelected(null)}
        onOk={() => void apply()}
        confirmLoading={busy}
        okText="Отправить заявку"
        cancelText="Отмена"
      >
        <p className="subtle">
          Администратор увидит ваше имя, выбранные роли и сообщение. Права
          участника появятся после одобрения.
        </p>
        <Form form={form} name="membership_application" layout="vertical">
          <Form.Item name="role_ids" label="В каких ролях хотите служить">
            <Select
              mode="multiple"
              options={selected?.roles.map((role) => ({
                value: role.id,
                label: role.name,
              }))}
            />
          </Form.Item>
          <Form.Item name="message" label="Сообщение администратору">
            <Input.TextArea rows={4} maxLength={2000} />
          </Form.Item>
        </Form>
        {error && <Alert type="error" message={error} />}
      </Modal>
    </section>
  );
}
