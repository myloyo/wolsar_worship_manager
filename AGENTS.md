# Repository Guidelines

## Project Structure & Module Organization

The repository has three services:

- `backend/`: Python 3.12+ FastAPI, PostgreSQL, migrations, and pytest tests.
- `frontend/`: React, TypeScript, SCSS, and Ant Design; source in `src/`.
- `bot_service/`: Telegram polling and delivery; calls backend APIs without database access.

Keep the Telegram service modular: `config.py` for settings, `clients.py` for external HTTP calls, `keyboards.py` for presentation, `handlers/` for messages/callbacks/update dispatch, `workers/` for polling and notification delivery, and `observability.py` for logging. Keep `main.py` limited to startup and task lifecycle. Do not put the service back into one large file or duplicate backend business rules in bot handlers.

Backend source is `backend/worship_bot/`: `api/` contains HTTP endpoints, schemas, security and dependencies; `application/` owns services and commands; `domain/` holds entities; `infrastructure/` handles persistence and integrations. Keep business rules in backend. Routers contain functions and route registration; request/response classes belong in schemas. Migrations and tests live in `backend/migrations/` and `backend/tests/`.

Root Compose files orchestrate services; `.github/workflows/` holds CI/CD. Root `.env` is ignored by Git. Never place API keys in frontend code or `VITE_*` variables.

## Build, Test, and Development Commands

From `backend/`: `poetry install --with dev`, `poetry run alembic upgrade head`, then `poetry run uvicorn worship_bot.main:app --reload`.

From `frontend/`: `npm ci`, `npm run dev`; `npm test`, `npm run build`, and `npm run format:check` verify changes.

From root: `docker compose up --build -d`. The Telegram bot starts with the rest of the application. `docker compose --env-file .env --env-file .env.test -f compose.yaml -f compose.test.yaml --profile test run --build --rm test-runner` runs PostgreSQL tests.

Backend checks: `poetry run pytest -q`, `poetry run mypy`, and `poetry run ruff check --config pyproject.toml worship_bot tests migrations ../bot_service ../deploy`. Format and check formatting with Ruff using `--config pyproject.toml` for these same directories; frontend uses Prettier.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions/modules, `PascalCase` classes, and strict type annotations. Ruff targets Python 3.12 with a 100-character line limit. Follow existing async patterns and numbered migrations, e.g. `0006_event_lifecycle.py`.

- Keep code simple; avoid unnecessary abstractions and boilerplate.
- Do not prefix methods with a single underscore. Preserve Python special methods like `__init__`.
- Avoid `_` placeholders in unpacking and dependency parameters. Retrieve needed values or use meaningful names.
- Use route/router `dependencies=[Depends(...)]` for checks with unused results, instead of `_: BotAuthorization`.
- Do not put module docstrings at the beginning of files, including initializers and migration templates.

## Testing Guidelines

Use pytest and pytest-asyncio (automatic async mode), `test_*.py` files, and `test_*` functions. No test classes or `unittest.TestCase`. Use function fixtures, protocol-based `AsyncMock`, and HTTPX; no fake repository classes in `conftest.py`.

Follow AAA: Arrange inputs/mocks, Act, then Assert results/calls. Separate phases with blank lines and concise comments. Fixtures can provide Arrange; `pytest.raises` can combine Act/Assert. Split independent scenarios; keep cleanup in fixtures or `finally`.

Run `poetry run pytest -q`. PostgreSQL tests skip without `TEST_DATABASE_URL`; `docker compose --env-file .env --env-file .env.test -f compose.yaml -f compose.test.yaml --profile test run --build --rm test-runner` provisions a separate database and applies migrations. No coverage threshold is configured.

## Commit & Pull Request Guidelines

Use Conventional Commits: `<type>(<optional scope>): <description>`. Use an imperative description and an appropriate type such as `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `build`, `perf`, or `chore`. Examples: `feat(calendar): add event deletion`, `fix(notifications): respect event subscriptions`, and `refactor(bot): split update handlers`. Mark breaking changes with `!` and explain them in a `BREAKING CHANGE:` footer when applicable.

PRs should describe behavior, link issues, report checks, and explain migration/configuration changes.

## Security & Configuration

Use the root `.env` for settings; commit only placeholder templates such as `.env.example` and `.env.test.example`. Never commit or log credentials, `BOT_SERVICE_TOKEN`, or `JWT_SECRET`. Use a dedicated test database.

Keep real environment files, private keys, database files/dumps, backups, logs, uploaded user data, deployment archives, local tools, caches, and dependencies out of Git and Docker build contexts. Preserve the publish check in `deploy/check_publish.py` and run it on staged files before publishing. CI must use disposable test credentials and mocked external services, not production secrets.

Public project documentation should cover the product, architecture, local development, and GitHub CI. Do not add deployment instructions, server addresses, or private operational notes to published documentation. Keep local server instructions such as `DEPLOYMENT.md` and `deploy/UPDATE_*.md` ignored by Git.

## Product and Permission Rules

Keep these rules in backend authorization and validation as well as in the UI; hiding a button is not an access check.

- Separate account access levels (member, coordinator, administrator) from ministry roles. Administrators and coordinators must be able to assign ministry roles to participants, including themselves. An administrator may also serve as a sound engineer or in another ministry role.
- All ministry members can view every event in their ministry's monthly calendar and its full details. Default to all events; provide an optional "Только с моим участием" filter. Match personal assignments by user identity, not merely by having the same role.
- Do not allow creating events in the past. Validate dates on both backend and frontend using the event timezone.
- Administrators and coordinators can delete events from the calendar with a clear UI confirmation. Deleting one occurrence must not delete other events in its recurring series. Remove related assignments and notification jobs atomically.
- Newly created worship events start with nine unassigned slots: one lead vocalist, two backing vocalists, drums, bass, electric guitar, acoustic guitar, keys, and sound engineer. Apply this to manual creation, templates, and reviewed assistant drafts. Extra backing vocals or other slots are added explicitly; preserve existing assignments and avoid duplicate slots.
- Event-kind eligibility is a strict restriction per participant's ministry role, not a scheduling preference. Administrators and coordinators can edit it in the participant card. Support Sunday services, praise and prayer evenings (ВХМ), prayer meetings, general leaders' meetings (ОЛ), and other events. An empty restriction list allows all kinds. Enforce eligibility for manual assignments, self-signup, and assistant draft application; reject changes incompatible with existing future assignments until those assignments are resolved.
- Only the lead vocalist assigned to that particular event can change its song list and clothing notes. Administrator access alone does not grant this permission. Save with revision checks and notify subscribed participants about actual changes; unchanged content must not create duplicate notifications.

## Participation and Notifications

- The personal assignments section is named "Доступность". Clicking an event there opens its full details, including the team, rehearsal, songs, and clothing, even when it belongs to another month or another ministry the user belongs to.
- Show each participant's response status in the event composition. Use a clock for awaiting a response, a check for confirmed participation, and a distinct visible replacement-request status. Icons need accessible labels or tooltips.
- "Запросить замену" remains available after confirming participation. It replaces the refusal action for an existing assignment. Keep the person assigned until a coordinator or administrator appoints a replacement; notify the coordinators and administrators of that ministry. Repeated requests must be idempotent. A new assignment resets the response/replacement status and requires the new participant's confirmation. Continue checking ownership, assignment revision, and event dates.
- Make notification settings available to every user regardless of access level or whether they have enabled notifications. Keep an obvious entry in "Доступность" and in account settings. Offer notification setup after login, while respecting the user's browser permission choice.
- Personal event notifications default to enabled for events the user participates in and disabled for other events. Let ministry members subscribe to other events or mute individual events. Respect the preference during both queuing and delivery in Telegram and Web Push. Replacement requests to responsible coordinators and administrators are operational alerts and must not be suppressed by their personal event subscription.
- Distinguish the five-minute, single-use login link from the authenticated session. The current default session lifetime is seven days (`JWT_LIFETIME_MINUTES=10080`), configurable through environment settings. Do not shorten the session to the login link's lifetime.

## Interface Rules

- Design primarily for mobile, while checking laptop layouts too. Avoid overlapping text, cramped buttons, clipped controls, and compressed sidebar content.
- For an ordinary ministry member, bottom navigation contains only "Расписание", "Доступность", and "Участники", with icons and labels. Open account settings from the user avatar at the top right. Do not make "Церкви и команды" the ordinary member's default landing screen after joining a ministry; show relevant personal assignments instead.
- Render the month as a calendar grid rather than a list. Clicking a date shows that day's events; clicking an event opens its details and permitted editing controls. Preserve the table composition view familiar from the team's previous spreadsheet workflow.
- In assignment rows, show the full role name, response status, and one person-selection field. Do not duplicate the person's name in a separate edit field. Icons may replace text only when their meaning is accessible.
- The assistant's attachment control is called "Вложения", not "История". Keep clear spacing around its controls and working indicator.
- Preserve the supplied avatar favicon at `frontend/public/favicon.ico` and its reference in `frontend/index.html`.

## Logging and Monitoring

Keep API, Telegram bot, and Web Push worker logs structured as single-line JSON on stdout with consistent fields. Include UTC timestamp, level, service, stable event code, and relevant technical identifiers. Correlate bot-to-backend calls with `request_id`/`X-Request-ID`.

Cover incoming HTTP requests, bot updates and handled failures, outbound provider calls, background jobs, notification delivery and retries, and service lifecycle. Record status/outcome and duration where relevant. Central boundary logging should cover operations without adding noisy logs to every pure formatting or keyboard helper. Preserve Docker log rotation and configurable `LOG_LEVEL`.

Never log authorization headers, cookies, passwords, tokens, login links, request/response bodies, message text, uploaded history, push subscription endpoints, or SQL parameters. Use route templates rather than raw URLs or query strings. Export only approved metadata; error diagnostics may include exception type and stack locations, but not exception messages or local variables that can contain secrets. Keep third-party HTTP/SQL logs from leaking credentials, including at DEBUG level. Mock external services when testing logging and verify that secret values stay out of output.

## Assistant and Deployment

Keep generated schedules as reviewed drafts. Check permissions, membership, roles, dates, revision, and occupied slots before applying changes atomically. Treat uploaded history as untrusted data. Mock external OpenAI/Telegram calls in tests; do not use real tokens for automated checks. CI publishes images after successful main-branch checks. Production deployment requires a configured server and GitHub environment secrets.

Keep local verification distinct from production deployment and report where changes were actually applied. After testing, stop and clean up only the temporary servers, containers, and Docker session started for that verification; do not stop the user's pre-existing services.
