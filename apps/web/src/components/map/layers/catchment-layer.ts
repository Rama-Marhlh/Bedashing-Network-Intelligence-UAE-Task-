import type { LayerSpecification } from "maplibre-gl";

import { COLORS } from "@/config/theme";

export const CATCHMENT_LAYER_IDS = {
  5: "catchments-5",
  10: "catchments-10",
  15: "catchments-15",
} as const;

const colors = { 5: COLORS.catchment5, 10: COLORS.catchment10, 15: COLORS.catchment15 };

export const catchmentLayers = ([5, 10, 15] as const).map((minutes): LayerSpecification => ({
  id: CATCHMENT_LAYER_IDS[minutes],
  type: "fill",
  source: "catchments",
  filter: ["==", ["get", "travel_minutes"], minutes],
  paint: {
    "fill-color": colors[minutes],
    "fill-opacity": minutes === 10 ? 0.16 : 0.1,
    "fill-outline-color": colors[minutes],
  },
}));
