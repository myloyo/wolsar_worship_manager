import { afterEach, expect, it, vi } from "vitest";
import { api, json } from "./api";

afterEach(() => vi.unstubAllGlobals());
it("sends JSON with same-origin session cookies", async () => {
  // Arrange
  const fetchMock = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetchMock);
  // Act
  const result = await api<{ id: number }>(
    "/portal/me",
    json("PUT", { name: "Anna" }),
  );
  // Assert
  expect(result.id).toBe(1);
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/portal/me",
    expect.objectContaining({ credentials: "same-origin", method: "PUT" }),
  );
});
it("shows a server permission error", async () => {
  // Arrange
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: "Forbidden" }), { status: 403 }),
      ),
  );
  // Act / Assert
  await expect(api("/portal/me")).rejects.toThrow("Forbidden");
});
