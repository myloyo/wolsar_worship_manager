import { afterEach, expect, it, vi } from "vitest";
import { initialTheme, themeStorageKey } from "./themes";

afterEach(() => vi.unstubAllGlobals());

it("restores a saved theme before the system preference", () => {
  // Arrange
  const getItem = vi.fn().mockReturnValue("plum");
  vi.stubGlobal("localStorage", { getItem });
  vi.stubGlobal("matchMedia", () => ({ matches: false }));

  // Act
  const selected = initialTheme();

  // Assert
  expect(selected).toBe("plum");
  expect(getItem).toHaveBeenCalledWith(themeStorageKey);
});

it("ignores an unknown saved theme and follows the system", () => {
  // Arrange
  vi.stubGlobal("localStorage", { getItem: () => "unknown" });
  vi.stubGlobal("matchMedia", () => ({ matches: true }));

  // Act
  const selected = initialTheme();

  // Assert
  expect(selected).toBe("dark");
});

it("works when browser storage is unavailable", () => {
  // Arrange
  vi.stubGlobal("localStorage", {
    getItem: () => {
      throw new Error("Storage blocked");
    },
  });
  vi.stubGlobal("matchMedia", () => ({ matches: false }));

  // Act
  const selected = initialTheme();

  // Assert
  expect(selected).toBe("light");
});
