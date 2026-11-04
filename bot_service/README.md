# Telegram service

Бот получает обновления Telegram и вызывает HTTP API backend. Он не имеет доступа
к PostgreSQL. Членство, права, назначения, ограничения и изменения расписания
проверяет backend; бот отвечает за транспорт и представление сообщений.

```text
bot_service/
  main.py                  # конфигурация запуска, жизненный цикл двух задач
  config.py                # настройки окружения
  clients.py               # Telegram и backend, сетевые ошибки, корреляция
  keyboards.py             # формирование inline-клавиатур и ссылок
  observability.py         # JSON-формат логов и контекст запроса
  handlers/
    messages.py            # команды личного чата
    callbacks.py           # нажатия кнопок
    updates.py             # диспетчеризация обновления и общий журнал результата
  workers/
    polling.py             # long polling, offset, повтор соединения
    notifications.py       # получение очереди, доставка и отчёт backend
```

Направление зависимостей: запуск → фоновые задачи → обработчики → HTTP-клиенты.
Клавиатуры не обращаются к сети. Обработчики получают HTTP-клиент и настройки
аргументами; тесты используют HTTPX MockTransport без настоящего Telegram.
TaskGroup останавливает вторую задачу при аварийном завершении первой.
Повторные попытки сетевых операций остаются в фоновых задачах.

Команда запуска сохраняется: `python -m bot_service.main`.
Настройки: `TELEGRAM_BOT_TOKEN`, `BOT_SERVICE_TOKEN`, `BACKEND_URL`, `WEB_URL`,
`OFFSET_FILE`, `LOG_LEVEL`. Токены хранятся в SecretStr и не записываются в журнал.
Формат логов описан в [LOGGING.md](../LOGGING.md).

Проверки из `backend/`: `poetry run pytest -q tests/test_bot_service.py tests/test_observability.py`,
`poetry run mypy` и `poetry run ruff check --config pyproject.toml ../bot_service`.
