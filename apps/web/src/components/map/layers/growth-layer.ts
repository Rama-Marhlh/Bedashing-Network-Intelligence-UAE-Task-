import type { LayerSpecification } from "maplibre-gl";

import { COLORS } from "@/config/theme";

export const GROWTH_CLUSTER_LAYER_ID = "growth-clusters";
export const GROWTH_SHORTLIST_LAYER_ID = "growth-shortlist";

export const growthClusterLayer: LayerSpecification = {
  id: GROWTH_CLUSTER_LAYER_ID,
  type: "circle",
  source: "growth-clusters",
  paint: {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 3, 12, 7],
    "circle-color": COLORS.grow,
    "circle-opacity": 0.58,
    "circle-stroke-color": "#ecfeff",
    "circle-stroke-width": 1,
  },
};

export const growthShortlistLayer: LayerSpecification = {
  id: GROWTH_SHORTLIST_LAYER_ID,
  type: "circle",
  source: "growth-shortlist",
  paint: {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 7, 12, 12],
    "circle-color": COLORS.grow,
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": 3,
  },
};

export const growthShortlistLabelLayer: LayerSpecification = {
  id: "growth-shortlist-rank",
  type: "symbol",
  source: "growth-shortlist",
  layout: {
    "text-field": ["to-string", ["get", "shortlist_rank"]],
    "text-size": 11,
    "text-font": ["Noto Sans Bold"],
    "text-allow-overlap": true,
  },
  paint: { "text-color": "#ffffff" },
};
