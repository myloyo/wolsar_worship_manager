import { useEffect, useState } from "react";
import { Alert, Button, Modal, Space } from "antd";
import {
  enableNotifications,
  supportsPush,
  syncNotifications,
} from "../notifications";

export default function NotificationPrompt({ userId }: { userId: number }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = `wolsar.notification-prompt.${userId}`;
  useEffect(() => {
    let active = true;
    void syncNotifications()
      .then((enabled) => {
        if (active && !enabled && !sessionStorage.getItem(key)) setOpen(true);
      })
      .catch(() => {
        if (active && !sessionStorage.getItem(key)) setOpen(true);
      });
    return () => {
      active = false;
    };
  }, [key]);
  const close = () => {
    sessionStorage.setItem(key, "seen");
    setOpen(false);
  };
  const enable = async () => {
    setBusy(true);
    setError("");
    try {
      await enableNotifications();
      close();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Не удалось включить уведомления",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Не пропустите своё служение"
      open={open}
      closable={false}
      maskClosable={false}
      footer={null}
    >
      <p>
        Включите уведомления о назначениях, репетициях и изменениях песен или
        одежды.
      </p>
      {!supportsPush() && (
        <Alert
          type="info"
          message="На iPhone добавьте сайт на домашний экран через меню «Поделиться» и откройте его оттуда. В других браузерах проверьте поддержку уведомлений."
        />
      )}
      {error && <Alert type="warning" message={error} />}
      <Space wrap style={{ marginTop: 20 }}>
        <Button type="primary" loading={busy} onClick={() => void enable()}>
          Включить уведомления
        </Button>
        <Button disabled={busy} onClick={close}>
          Позже
        </Button>
      </Space>
      <p className="subtle">Настройки всегда доступны в «Моей карточке».</p>
    </Modal>
  );
}
