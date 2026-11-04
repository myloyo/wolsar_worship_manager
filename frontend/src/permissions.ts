import type { Ministry } from "./types";
export function hasPermission(
  ministry: Ministry | undefined,
  permission: string,
): boolean {
  return ministry?.permissions.includes(permission) ?? false;
}

export const accessNames: Record<string, string> = {
  member: "Участник",
  coordinator: "Координатор",
  admin: "Администратор",
  developer: "Разработчик",
};
