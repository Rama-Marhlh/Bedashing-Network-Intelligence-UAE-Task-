import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { loadCoreDashboardData, loadWhitespaceData } from "@/lib/app-data/loaders";

const root = resolve(import.meta.dirname, "..", "..", "..");

afterEach(() => vi.unstubAllGlobals());

describe("static application-data loading", () => {
  it("loads and validates the core snapshot without requesting whitespace", async () => {
    const requested: string[] = [];
    vi.stubGlobal("fetch", async (input: string | URL | Request) => {
      const url = String(input);
      requested.push(url);
      const filename = url.split("/").at(-1);
      if (!filename) return new Response(null, { status: 404 });
      return new Response(await readFile(resolve(root, "app_data", filename)), { status: 200 });
    });

    const data = await loadCoreDashboardData();

    expect(data.branches.features).toHaveLength(24);
    expect(data.growthShortlist.features).toHaveLength(10);
    expect(requested).not.toContain("/app_data/whitespace.geojson");
  });

  it("loads whitespace only through its dedicated loader", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(await readFile(resolve(root, "app_data", "whitespace.geojson")), {
          status: 200,
        }),
    );

    expect((await loadWhitespaceData()).features).toHaveLength(5548);
  });
});
