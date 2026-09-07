import type { LayerSpecification } from "maplibre-gl";

import { COLORS } from "@/config/theme";

export const BRANCH_LAYER_ID = "bedashing-branches";

export const branchLayer: LayerSpecification = {
  id: BRANCH_LAYER_ID,
  type: "circle",
  source: "branches",
  paint: {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 6, 12, 10],
    "circle-color": [
      "match",
      ["get", "recommendation"],
      "PROTECT",
      COLORS.protect,
      "HOLD",
      COLORS.hold,
      "SHRINK",
      COLORS.shrink,
      "#334155",
    ],
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": 2,
    "circle-opacity": 0.96,
  },
};
