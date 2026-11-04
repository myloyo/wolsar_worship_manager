# Product direction

The product helps churches organize ministry schedules and retain related information.

## Participants

- View their ministry schedule as a table in a web application.
- View the team, song list, notes, and checklists for each event.
- Receive assignment, removal, and change notifications through Telegram/VK.
- Receive rehearsal and event reminders, including multiple offsets such as one day and two hours.
- Visibility of other ministries' schedules remains an open product decision.

## Target architecture

- Core backend owns business rules, schedules, memberships, permissions, and event information.
- Bot service handles Telegram/VK conversations and notification delivery through core APIs.
- Web application provides participant and coordinator interfaces through the same core APIs.
- Keep scheduling rules out of clients. Introduce service boundaries incrementally.

## Implementation stages

1. Finish and test core event participation, invitations, rehearsals, and song history APIs.
2. Provide a personal schedule endpoint and consistent authorization for existing endpoints.
3. Add structured notes/checklists and event change notifications.
4. Support multiple reminder offsets and a delivery worker with retry handling.
5. Add Telegram/VK clients and a web schedule interface.
6. Add availability and automatic scheduling rules after requirements are agreed.

A queue entry is not a delivered notification. A service method without a wired API is not a completed user workflow.

## Current delivery

The repository is split into backend, frontend, and bot_service. The web portal provides profile,
ministry schedule, roster, scoped controls, rehearsals, and an administrator planning dialog.
The assistant accepts XLSX/CSV/text/images and produces persisted proposals for explicit application.
Telegram registration, one-time web login, profile, schedule, and notification delivery are implemented.
VK delivery is still pending. The exposed OpenAI key must be replaced before live model validation.
CI and container publishing are configured; deployment awaits a server/domain and environment secrets.

## Brand and onboarding follow-up

The portal uses supplied Stolzl and IF Kica fonts and Wolsar Worship brand assets.
Five persistent interface themes cover login, schedule, assistant, and the separate profile page.
Registration applications with ministry approval, issued usernames/password login, church/ministry
setup in the portal, and Google Sheets URL import are still pending; file/image history uploads
and the administrator assistant dialog already exist.

## Local administration and web notifications

Docker runtime and checks use separate Compose/env files. A server-local bootstrap command creates
an initial ministry administrator and one-time login; administrators can create participant cards
with scoped roles and promote other members in their ministry. Demoting the last admin is blocked.
Browser push subscriptions, permission sync, delivery checks, a service worker, and an independent
retrying worker are implemented. Roster badges show active, absent, or stale subscription checks;
OS-level notification blocking and actual user delivery/read receipts are not detectable.
Public registration applications and linking manually created cards to Telegram remain pending.

## Account access update

Existing users can configure web credentials in their profile and log in without Telegram.
Password hashes use scrypt and random salts; password changes require the current password;
failed login attempts have a cooldown. The server-local one-time link command remains the
initial access path for an existing unlinked account. Telegram now starts in the default Compose
stack. A VK transport and self-service linking of an existing web account remain pending.
