import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar";
import { demoProfile } from "../demo";

describe("навигация служителя", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("оставляет три раздела и доступ к профилю через пользователя", () => {
    vi.stubGlobal("location", { search: "" });
    const markup = renderToStaticMarkup(
      <Sidebar
        profile={demoProfile}
        ministry={{ ...demoProfile.ministries[0], access_level: "member" }}
        tab="schedule"
        eventCount={3}
        memberCount={5}
        onTab={() => {}}
        onProfile={() => {}}
        onLogout={() => {}}
      />,
    );
    const nav = markup.match(/<nav[^>]*>([\s\S]*?)<\/nav>/)?.[1] || "";
    expect(nav.match(/<button/g)).toHaveLength(3);
    expect(nav).toContain("Расписание");
    expect(nav).toContain("Доступность");
    expect(nav).toContain("Участники");
    expect(nav).not.toContain("Моя карточка");
    expect(nav).not.toContain("Церкви и команды");
    expect(markup).toContain('class="user-menu"');
  });
});
