import type { LayerSpecification } from "maplibre-gl";

import { COLORS } from "@/config/theme";

export const WHITESPACE_LAYER_ID = "whitespace-opportunities";
export const SELECTED_WHITESPACE_LAYER_ID = "selected-whitespace-opportunity";

export const whitespaceLayer: LayerSpecification = {
  id: WHITESPACE_LAYER_ID,
  type: "fill",
  source: "whitespace",
  paint: {
    "fill-color": [
      "match",
      ["get", "recommendation"],
      "GROW",
      COLORS.grow,
      "WATCH",
      COLORS.watch,
      COLORS.skip,
    ],
    "fill-opacity": ["match", ["get", "recommendation"], "GROW", 0.34, "WATCH", 0.22, 0.08],
    "fill-outline-color": "rgba(255,255,255,0.28)",
  },
};

export const selectedWhitespaceLayer: LayerSpecification = {
  id: SELECTED_WHITESPACE_LAYER_ID,
  type: "line",
  source: "whitespace",
  filter: ["==", ["get", "h3_cell"], ""],
  paint: {
    "line-color": "#111827",
    "line-width": 4,
    "line-opacity": 1,
  },
};
