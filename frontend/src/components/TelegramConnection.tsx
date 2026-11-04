import { useEffect, useState } from "react";
import { Alert, Button, Space, Tag } from "antd";
import { api } from "../api";
export default function TelegramConnection({ demo }: { demo: boolean }) {
  const [linked, setLinked] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    if (demo) return;
    try {
      const state = await api<{
        telegram_linked: boolean;
        telegram_username: string | null;
      }>("/portal/me/accounts");
      setLinked(state.telegram_linked);
      setUsername(state.telegram_username);
      if (state.telegram_linked) setUrl("");
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось проверить привязку",
      );
    }
  };
  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [demo]);
  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ url: string }>("/portal/me/telegram-link", {
        method: "POST",
      });
      setUrl(result.url);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось создать ссылку",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel profile-form-panel">
      <div className="section-heading">
        <h2>Telegram</h2>
        <p>
          Привяжите свой Telegram к этому аккаунту для входа через бота и
          напоминаний.
        </p>
      </div>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Tag color={linked ? "success" : "default"}>
          {linked
            ? `Привязан${username ? " @" + username : ""}`
            : "Пока не привязан"}
        </Tag>
        {error && <Alert type="error" message={error} />}
        {!linked && (
          <Button disabled={demo} loading={busy} onClick={() => void connect()}>
            {url ? "Получить новую ссылку" : "Привязать Telegram"}
          </Button>
        )}
        {url && (
          <>
            <Button type="primary" href={url} target="_blank" rel="noreferrer">
              Открыть @wolsar_worship_bot
            </Button>
            <p className="subtle">
              Нажмите «Начать» в боте. Ссылка действует 10 минут и используется
              один раз. После привязки нажмите «Проверить привязку».
            </p>
            <Button onClick={() => void load()}>Проверить привязку</Button>
          </>
        )}
        {demo && (
          <p className="subtle">
            Привязка доступна в вашем собственном аккаунте.
          </p>
        )}
      </Space>
    </section>
  );
}
