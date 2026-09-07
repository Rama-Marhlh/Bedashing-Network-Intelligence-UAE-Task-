import type {
  AppManifest,
  Branch,
  Catchment,
  Competitor,
  DataQualityReport,
  GrowthCandidate,
  GrowthCluster,
  GrowthOpportunity,
  NetworkSummary,
} from "@bedashing/data-contract";
import type { Feature, FeatureCollection, Geometry } from "geojson";

export type AppFeature<T> = Feature<Geometry, T> & { id: string };
export type AppFeatureCollection<T> = FeatureCollection<Geometry, T>;

export interface CoreDashboardData {
  manifest: AppManifest;
  summary: NetworkSummary;
  quality: DataQualityReport;
  branches: AppFeatureCollection<Branch>;
  catchments: AppFeatureCollection<Catchment>;
  competitors: AppFeatureCollection<Competitor>;
  growthClusters: AppFeatureCollection<GrowthCluster>;
  growthShortlist: AppFeatureCollection<GrowthCandidate>;
}

export type WhitespaceData = AppFeatureCollection<GrowthOpportunity>;

export type SelectedMapFeature =
  | { kind: "branch"; properties: Branch }
  | { kind: "competitor"; properties: Competitor }
  | { kind: "growth-candidate"; properties: GrowthCandidate; coordinates?: [number, number] }
  | { kind: "growth-cluster"; properties: GrowthCluster }
  | { kind: "whitespace"; properties: GrowthOpportunity };
