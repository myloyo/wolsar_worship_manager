export type Ministry = {
  id: number;
  name: string;
  church_name: string;
  access_level: string;
  permissions: string[];
};
export type Profile = {
  id: number;
  name: string;
  surname: string;
  birthday_date: string | null;
  ministries: Ministry[];
};
export type Role = {
  id: number;
  name: string;
  user_ministry_role_id: number;
  allowed_event_kinds?: string[];
};
export type Member = {
  id: number;
  name: string;
  surname: string;
  access_level: string;
  roles: Role[];
  notification_status?: "enabled" | "needs_setup" | "needs_check";
  notifications_checked_at?: string | null;
};
export type Slot = {
  id: number;
  ministry_role_id: number;
  slot_number: number;
  user_ministry_role_id: number | null;
  confirmation_status: string;
};
export type CalendarEvent = {
  church_ministry_id?: number;
  event_kind?: string;
  songs_text?: string;
  clothing_text?: string;
  content_revision?: number;
  event_id: number;
  event_name: string;
  starts_at: string;
  additional_info: string | null;
  rehearsal_at: string | null;
  event_reminder_at: string | null;
  rehearsal_reminder_at: string | null;
  song_ids: number[];
  role_slots: Slot[];
};
export type PlannedEvent = {
  existing_event_id: number | null;
  event_name: string;
  starts_at: string;
  additional_info: string | null;
  assignments: { ministry_role_id: number; user_ministry_role_id: number }[];
  extra_role_ids?: number[];
};
export type Proposal = {
  reply: string;
  warnings: string[];
  events: PlannedEvent[];
};
export type ChatSession = {
  id: string;
  month: string;
  revision: number;
  messages: { role: string; content: string }[];
  proposal: Proposal | null;
  attachment_count: number;
};
