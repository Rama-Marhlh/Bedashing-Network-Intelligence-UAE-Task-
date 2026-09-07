import {
  appManifestSchema,
  branchSchema,
  catchmentSchema,
  competitorSchema,
  dataQualitySchema,
  geoJsonFeatureCollectionSchema,
  growthCandidateSchema,
  growthClusterSchema,
  growthOpportunitySchema,
  networkSummarySchema,
} from "@bedashing/data-contract";
import type { AppFeatureCollection, CoreDashboardData, WhitespaceData } from "@/types/app-data";

type SchemaLike<T> = { parse: (input: unknown) => T };

const APP_DATA_ROOT = "/app_data";

export class AppDataLoadError extends Error {
  constructor(filename: string, cause?: unknown) {
    super(`Unable to load validated application data: ${filename}`, { cause });
    this.name = "AppDataLoadError";
  }
}

async function fetchJson(filename: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`${APP_DATA_ROOT}/${filename}`, { signal, cache: "force-cache" });
  if (!response.ok) throw new AppDataLoadError(filename);
  return response.json();
}

async function loadDocument<T>(
  filename: string,
  schema: SchemaLike<T>,
  signal?: AbortSignal,
): Promise<T> {
  try {
    return schema.parse(await fetchJson(filename, signal));
  } catch (error) {
    if (error instanceof AppDataLoadError) throw error;
    throw new AppDataLoadError(filename, error);
  }
}

async function loadCollection<T>(
  filename: string,
  propertySchema: SchemaLike<T>,
  signal?: AbortSignal,
): Promise<AppFeatureCollection<T>> {
  const document = geoJsonFeatureCollectionSchema.parse(await fetchJson(filename, signal));
  const features = document.features.map((feature) => ({
    ...feature,
    properties: propertySchema.parse(feature.properties),
  }));
  return { type: "FeatureCollection", features } as AppFeatureCollection<T>;
}

export async function loadCoreDashboardData(signal?: AbortSignal): Promise<CoreDashboardData> {
  const [manifest, summary, quality, branches, catchments, competitors, growthClusters, shortlist] =
    await Promise.all([
      loadDocument("app_manifest.json", appManifestSchema, signal),
      loadDocument("network_summary.json", networkSummarySchema, signal),
      loadDocument("data_quality.json", dataQualitySchema, signal),
      loadCollection("branches.geojson", branchSchema, signal),
      loadCollection("catchments.geojson", catchmentSchema, signal),
      loadCollection("competitors.geojson", competitorSchema, signal),
      loadCollection("growth_clusters.geojson", growthClusterSchema, signal),
      loadCollection("top_10_growth_shortlist.geojson", growthCandidateSchema, signal),
    ]);
  return {
    manifest,
    summary,
    quality,
    branches,
    catchments,
    competitors,
    growthClusters,
    growthShortlist: shortlist,
  };
}

export const loadWhitespaceData = (signal?: AbortSignal): Promise<WhitespaceData> =>
  loadCollection("whitespace.geojson", growthOpportunitySchema, signal);
