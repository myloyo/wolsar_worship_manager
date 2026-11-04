import { describe, expect, it } from "vitest";
import { hasPermission } from "./permissions";
import type { Ministry } from "./types";

describe("ministry permissions", () => {
  it("hides manager and assistant actions for a member", () => {
    // Arrange
    const ministry: Ministry = {
      id: 1,
      name: "Worship",
      church_name: "Church",
      access_level: "member",
      permissions: ["view_schedule", "view_members", "self_signup"],
    };
    // Act
    const canManage = hasPermission(ministry, "manage_events");
    const canPlan = hasPermission(ministry, "use_assistant");
    // Assert
    expect(canManage).toBe(false);
    expect(canPlan).toBe(false);
  });
  it("uses server permissions rather than trusting a role name", () => {
    // Arrange
    const ministry: Ministry = {
      id: 1,
      name: "Worship",
      church_name: "Church",
      access_level: "admin",
      permissions: [],
    };
    // Act
    const allowed = hasPermission(ministry, "use_assistant");
    // Assert
    expect(allowed).toBe(false);
  });
  it("denies actions when no ministry is selected", () => {
    // Act
    const allowed = hasPermission(undefined, "manage_events");
    // Assert
    expect(allowed).toBe(false);
  });
});
