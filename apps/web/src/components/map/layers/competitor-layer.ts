import type { LayerSpecification } from "maplibre-gl";

import { COLORS } from "@/config/theme";

export const DIRECT_COMPETITOR_LAYER_ID = "competitors-direct";
export const ADJACENT_COMPETITOR_LAYER_ID = "competitors-adjacent";

const competitorLayer = (
  id: string,
  tier: "DIRECT" | "ADJACENT",
  color: string,
): LayerSpecification => ({
  id,
  type: "circle",
  source: "competitors",
  filter: ["==", ["get", "competitor_tier"], tier],
  minzoom: 7,
  paint: {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 2.5, 13, 5],
    "circle-color": color,
    "circle-opacity": 0.72,
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": 0.7,
  },
});

export const competitorLayers = [
  competitorLayer(DIRECT_COMPETITOR_LAYER_ID, "DIRECT", COLORS.directCompetitor),
  competitorLayer(ADJACENT_COMPETITOR_LAYER_ID, "ADJACENT", COLORS.adjacentCompetitor),
];
