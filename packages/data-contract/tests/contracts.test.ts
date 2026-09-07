import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  branchSchema,
  catchmentSchema,
  competitorSchema,
  confidenceIndicatorSchema,
  dataSourceSchema,
  geoJsonFeatureCollectionSchema,
  growthCandidateSchema,
  growthClusterSchema,
  growthOpportunitySchema,
  recommendationExplanationSchema,
} from "../src/index";

const packageRoot = resolve(import.meta.dirname, "..");
const repositoryRoot = resolve(packageRoot, "..", "..");
const load = (path: string): unknown =>
  JSON.parse(readFileSync(resolve(repositoryRoot, path), "utf8"));

describe("representative parity fixtures", () => {
  const fixture = load("packages/data-contract/fixtures/parity.json") as Record<string, unknown>;

  it("validates shared supporting contracts", () => {
    expect(confidenceIndicatorSchema.parse(fixture.confidence)).toBeDefined();
    expect(dataSourceSchema.parse(fixture.source)).toBeDefined();
    expect(recommendationExplanationSchema.parse(fixture.explanation)).toBeDefined();
  });
});

describe("canonical app data", () => {
  it.each([
    ["app_data/branches.geojson", branchSchema],
    ["app_data/catchments.geojson", catchmentSchema],
    ["app_data/competitors.geojson", competitorSchema],
    ["app_data/whitespace.geojson", growthOpportunitySchema],
    ["app_data/growth_clusters.geojson", growthClusterSchema],
    ["app_data/top_10_growth_shortlist.geojson", growthCandidateSchema],
  ] as const)("validates %s", (filename, propertySchema) => {
    const collection = geoJsonFeatureCollectionSchema.parse(load(filename));
    for (const feature of collection.features) propertySchema.parse(feature.properties);
  });
});
