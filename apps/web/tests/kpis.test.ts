import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  appManifestSchema,
  dataQualitySchema,
  networkSummarySchema,
} from "@bedashing/data-contract";
import { buildNetworkKpis } from "@/lib/dashboard/kpis";
import type { CoreDashboardData } from "@/types/app-data";

const root = resolve(import.meta.dirname, "..", "..", "..");
const load = (name: string): unknown =>
  JSON.parse(readFileSync(resolve(root, "app_data", name), "utf8"));

describe("network KPIs", () => {
  it("uses published snapshot values", () => {
    const data = {
      manifest: appManifestSchema.parse(load("app_manifest.json")),
      summary: networkSummarySchema.parse(load("network_summary.json")),
      quality: dataQualitySchema.parse(load("data_quality.json")),
    } as CoreDashboardData;
    const values = Object.fromEntries(
      buildNetworkKpis(data).map((item) => [item.label, item.value]),
    );

    expect(values).toMatchObject({
      "Total branches": "24",
      Protect: "7",
      Hold: "12",
      "Shrink / review": "5",
      "Observed competitors": "2,367",
      GROW: "1,727",
      WATCH: "1,222",
      SKIP: "2,599",
    });
  });
});
