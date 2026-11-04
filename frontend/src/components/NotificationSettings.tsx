import { useEffect, useState } from "react";
import { Alert, Button, Space, Tag } from "antd";
import { BellOutlined } from "@ant-design/icons";
import {
  checkNotification,
  disableNotifications,
  enableNotifications,
  supportsPush,
  syncNotifications,
} from "../notifications";

export default function NotificationSettings({ demo }: { demo: boolean }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  useEffect(() => {
    if (demo) return;
    const sync = () => {
      void syncNotifications()
        .then(setEnabled)
        .catch(() => setEnabled(false));
    };
    sync();
    window.addEventListener("focus", sync);
    return () => window.removeEventListener("focus", sync);
  }, [demo]);
  const change = async (action: "enable" | "disable" | "check") => {
    setBusy(true);
    setError("");
    setSent(false);
    try {
      if (action === "check") {
        await checkNotification();
        setSent(true);
      } else if (action === "enable") {
        await enableNotifications();
        setEnabled(true);
      } else {
        await disableNotifications();
        setEnabled(false);
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось настроить уведомления",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel profile-form-panel">
      <div className="section-heading">
        <h2>
          <BellOutlined /> Уведомления о служении
        </h2>
        <p>
          Назначения, изменения и напоминания о репетициях — на этом устройстве.
        </p>
      </div>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Tag color={enabled ? "success" : "warning"}>
          {enabled ? "Подключены на этом устройстве" : "Нужно включить"}
        </Tag>
        <p className="subtle">
          Разрешение проверяется при открытии сайта. В настройках телефона
          уведомления тоже должны быть разрешены. На iPhone добавьте сайт на
          домашний экран и откройте оттуда.
        </p>
        {!demo && !supportsPush() && (
          <Alert
            type="warning"
            message="Нужен поддерживаемый браузер и HTTPS. На компьютере можно проверять через localhost."
          />
        )}
        {demo && (
          <Alert
            type="info"
            message="Подключение доступно после входа в свой аккаунт."
          />
        )}
        {error && <Alert type="error" message={error} />}
        {sent && (
          <Alert
            type="success"
            message="Проверочное уведомление отправлено. Убедитесь, что оно появилось на устройстве."
          />
        )}
        <Space wrap>
          <Button
            type="primary"
            disabled={demo}
            loading={busy}
            onClick={() => void change(enabled ? "disable" : "enable")}
          >
            {enabled ? "Отключить на этом устройстве" : "Включить уведомления"}
          </Button>
          {enabled && (
            <Button disabled={busy} onClick={() => void change("check")}>
              Проверить доставку
            </Button>
          )}
        </Space>
      </Space>
    </section>
  );
}
