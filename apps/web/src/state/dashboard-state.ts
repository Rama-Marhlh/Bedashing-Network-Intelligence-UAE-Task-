import type {
  BranchRecommendation,
  CompetitorTier,
  GrowthRecommendation,
} from "@bedashing/data-contract";

import type { DashboardSection } from "@/config/navigation";
import type { SelectedMapFeature } from "@/types/app-data";
import type { BranchTab } from "@/types/intelligence";

export type CatchmentMinutes = 5 | 10 | 15;
export type LayerKey =
  | "branches"
  | "catchment5"
  | "catchment10"
  | "catchment15"
  | "directCompetitors"
  | "adjacentCompetitors"
  | "whitespace"
  | "growthClusters"
  | "growthShortlist";

export interface DashboardState {
  activeSection: DashboardSection;
  visibleLayers: Record<LayerKey, boolean>;
  branchRecommendations: BranchRecommendation[];
  competitorTiers: CompetitorTier[];
  whitespaceRecommendations: GrowthRecommendation[];
  selectedFeature: SelectedMapFeature | null;
  mapFitRequest: number;
  comparisonBranchIds: string[];
  rankedBranchIds: string[];
  branchTab: BranchTab;
  competitorOriginBranchId: string | null;
  relationshipFocus: {
    competitorId: string;
    branchId: string;
    travelMinutes: CatchmentMinutes;
  } | null;
}

export type DashboardAction =
  | { type: "toggle-layer"; layer: LayerKey }
  | { type: "select-catchment"; minutes: CatchmentMinutes }
  | { type: "toggle-branch-recommendation"; value: BranchRecommendation }
  | { type: "toggle-competitor-tier"; value: CompetitorTier }
  | { type: "toggle-whitespace-recommendation"; value: GrowthRecommendation }
  | { type: "select-feature"; feature: SelectedMapFeature | null }
  | { type: "fit-network" }
  | { type: "show-growth-cluster"; clusterId: string }
  | { type: "navigate-section"; section: DashboardSection }
  | { type: "set-comparison"; branchIds: string[] }
  | { type: "set-ranked"; branchIds: string[] }
  | { type: "open-branch-tab"; tab: BranchTab }
  | {
      type: "show-competitor-relationship";
      competitorId: string;
      branchId: string;
      travelMinutes: CatchmentMinutes;
    }
  | { type: "reset" };

const defaultLayers: Record<LayerKey, boolean> = {
  branches: true,
  catchment5: false,
  catchment10: true,
  catchment15: false,
  directCompetitors: true,
  adjacentCompetitors: false,
  whitespace: false,
  growthClusters: false,
  growthShortlist: true,
};

export function createInitialDashboardState(activeSection: DashboardSection): DashboardState {
  return {
    activeSection,
    visibleLayers: { ...defaultLayers },
    branchRecommendations: ["PROTECT", "HOLD", "SHRINK"],
    competitorTiers: ["DIRECT", "ADJACENT"],
    whitespaceRecommendations: ["GROW", "WATCH", "SKIP"],
    selectedFeature: null,
    mapFitRequest: 0,
    comparisonBranchIds: [],
    rankedBranchIds: [],
    branchTab: "overview",
    competitorOriginBranchId: null,
    relationshipFocus: null,
  };
}

function toggleValue<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function dashboardReducer(state: DashboardState, action: DashboardAction): DashboardState {
  switch (action.type) {
    case "toggle-layer":
      return {
        ...state,
        visibleLayers: {
          ...state.visibleLayers,
          [action.layer]: !state.visibleLayers[action.layer],
        },
      };
    case "select-catchment":
      return {
        ...state,
        visibleLayers: {
          ...state.visibleLayers,
          catchment5: action.minutes === 5,
          catchment10: action.minutes === 10,
          catchment15: action.minutes === 15,
        },
      };
    case "toggle-branch-recommendation":
      return {
        ...state,
        branchRecommendations: toggleValue(state.branchRecommendations, action.value),
      };
    case "toggle-competitor-tier":
      return { ...state, competitorTiers: toggleValue(state.competitorTiers, action.value) };
    case "toggle-whitespace-recommendation":
      return {
        ...state,
        whitespaceRecommendations: toggleValue(state.whitespaceRecommendations, action.value),
      };
    case "select-feature":
      return {
        ...state,
        selectedFeature: action.feature,
        branchTab: action.feature?.kind === "branch" ? "overview" : state.branchTab,
        competitorOriginBranchId:
          action.feature?.kind === "branch"
            ? action.feature.properties.branch_id
            : state.competitorOriginBranchId,
      };
    case "open-branch-tab":
      return { ...state, branchTab: action.tab };
    case "show-competitor-relationship":
      return {
        ...state,
        competitorOriginBranchId: action.branchId,
        relationshipFocus: {
          competitorId: action.competitorId,
          branchId: action.branchId,
          travelMinutes: action.travelMinutes,
        },
        visibleLayers: {
          ...state.visibleLayers,
          catchment5: action.travelMinutes === 5,
          catchment10: action.travelMinutes === 10,
          catchment15: action.travelMinutes === 15,
        },
        mapFitRequest: state.mapFitRequest + 1,
      };
    case "fit-network":
      return { ...state, mapFitRequest: state.mapFitRequest + 1 };
    case "show-growth-cluster":
      return { ...state, visibleLayers: { ...state.visibleLayers, growthClusters: true }, mapFitRequest: state.mapFitRequest + 1 };
    case "navigate-section":
      return { ...state, activeSection: action.section };
    case "set-comparison":
      return {
        ...state,
        comparisonBranchIds: [...new Set(action.branchIds)].slice(0, 4),
      };
    case "set-ranked":
      return {
        ...state,
        rankedBranchIds: action.branchIds,
        mapFitRequest: state.mapFitRequest + 1,
      };
    case "reset":
      return createInitialDashboardState(state.activeSection);
  }
}
