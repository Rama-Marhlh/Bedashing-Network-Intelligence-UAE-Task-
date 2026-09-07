"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { useEffect, useRef, useState } from "react";
import maplibregl, { type GeoJSONSource, type MapGeoJSONFeature } from "maplibre-gl";

import {
  branchSchema,
  competitorSchema,
  growthCandidateSchema,
  growthClusterSchema,
} from "@bedashing/data-contract";
import { branchLayer, BRANCH_LAYER_ID } from "@/components/map/layers/branch-layer";
import { CATCHMENT_LAYER_IDS, catchmentLayers } from "@/components/map/layers/catchment-layer";
import {
  ADJACENT_COMPETITOR_LAYER_ID,
  competitorLayers,
  DIRECT_COMPETITOR_LAYER_ID,
} from "@/components/map/layers/competitor-layer";
import {
  GROWTH_CLUSTER_LAYER_ID,
  GROWTH_SHORTLIST_LAYER_ID,
  growthClusterLayer,
  growthShortlistLabelLayer,
  growthShortlistLayer,
} from "@/components/map/layers/growth-layer";
import {
  selectedWhitespaceLayer,
  SELECTED_WHITESPACE_LAYER_ID,
  whitespaceLayer,
  WHITESPACE_LAYER_ID,
} from "@/components/map/layers/whitespace-layer";
import { MAP_ATTRIBUTION, MAP_STYLE, NETWORK_BOUNDS } from "@/config/map";
import { branchFilter, whitespaceFilter } from "@/lib/map/filters";
import type { DashboardAction, DashboardState, LayerKey } from "@/state/dashboard-state";
import type { CoreDashboardData, SelectedMapFeature, WhitespaceData } from "@/types/app-data";

const ANALYST_API_URL = process.env.NEXT_PUBLIC_ANALYST_API_URL ?? "http://127.0.0.1:8000";

interface MapCanvasProps {
  data: CoreDashboardData;
  whitespace: WhitespaceData | null;
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
}

const layerVisibility: Record<LayerKey, string[]> = {
  branches: [BRANCH_LAYER_ID],
  catchment5: [CATCHMENT_LAYER_IDS[5]],
  catchment10: [CATCHMENT_LAYER_IDS[10]],
  catchment15: [CATCHMENT_LAYER_IDS[15]],
  directCompetitors: [DIRECT_COMPETITOR_LAYER_ID],
  adjacentCompetitors: [ADJACENT_COMPETITOR_LAYER_ID],
  whitespace: [WHITESPACE_LAYER_ID],
  growthClusters: [GROWTH_CLUSTER_LAYER_ID],
  growthShortlist: [GROWTH_SHORTLIST_LAYER_ID, "growth-shortlist-rank"],
};

function preferEnglishBasemapLabels(map: maplibregl.Map) {
  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== "symbol" || !layer.layout?.["text-field"]) continue;
    map.setLayoutProperty(layer.id, "text-field", [
      "coalesce",
      ["get", "name:en"],
      ["get", "name_en"],
      ["get", "name:latin"],
      ["get", "name"],
    ]);
  }
}

function parseSelectedFeature(
  feature: MapGeoJSONFeature,
  whitespace?: WhitespaceData | null,
): SelectedMapFeature | null {
  if (feature.layer.id === BRANCH_LAYER_ID) {
    return { kind: "branch", properties: branchSchema.parse(feature.properties) };
  }
  if ([DIRECT_COMPETITOR_LAYER_ID, ADJACENT_COMPETITOR_LAYER_ID].includes(feature.layer.id)) {
    return { kind: "competitor", properties: competitorSchema.parse(feature.properties) };
  }
  if (feature.layer.id === GROWTH_SHORTLIST_LAYER_ID) {
    return {
      kind: "growth-candidate",
      properties: growthCandidateSchema.parse(feature.properties),
      coordinates: (feature.geometry as GeoJSON.Point).coordinates as [number, number],
    };
  }
  if (feature.layer.id === GROWTH_CLUSTER_LAYER_ID) {
    return { kind: "growth-cluster", properties: growthClusterSchema.parse(feature.properties) };
  }
  if (feature.layer.id === WHITESPACE_LAYER_ID) {
    // MapLibre omits null-valued GeoJSON properties from rendered features.
    // Resolve the canonical validated record by H3 rather than parsing that lossy projection.
    const h3Cell = String(feature.properties.h3_cell ?? "");
    const canonical = whitespace?.features.find(
      (item) => item.properties.h3_cell === h3Cell,
    )?.properties;
    return canonical ? { kind: "whitespace", properties: canonical } : null;
  }
  return null;
}

export function MapCanvas({ data, whitespace, state, dispatch }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const stateRef = useRef(state);
  const whitespaceRef = useRef(whitespace);
  const [mapReady, setMapReady] = useState(false);
  const [tileWarning, setTileWarning] = useState(false);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  stateRef.current = state;
  whitespaceRef.current = whitespace;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      bounds: NETWORK_BOUNDS,
      fitBoundsOptions: { padding: 48 },
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ customAttribution: MAP_ATTRIBUTION }));

    const warningTimer = window.setTimeout(() => {
      if (!map.loaded()) setTileWarning(true);
    }, 8000);
    map.on("style.load", () => {
      window.clearTimeout(warningTimer);
      preferEnglishBasemapLabels(map);
      map.addSource("catchments", { type: "geojson", data: data.catchments });
      for (const layer of catchmentLayers) map.addLayer(layer);
      map.addSource("competitors", { type: "geojson", data: data.competitors });
      for (const layer of competitorLayers) map.addLayer(layer);
      map.addSource("growth-clusters", { type: "geojson", data: data.growthClusters });
      map.addLayer(growthClusterLayer);
      map.addSource("growth-shortlist", { type: "geojson", data: data.growthShortlist });
      map.addLayer(growthShortlistLayer);
      map.addLayer(growthShortlistLabelLayer);
      map.addSource("branches", { type: "geojson", data: data.branches });
      map.addLayer(branchLayer);

      const interactiveLayers = [
        BRANCH_LAYER_ID,
        DIRECT_COMPETITOR_LAYER_ID,
        ADJACENT_COMPETITOR_LAYER_ID,
        GROWTH_SHORTLIST_LAYER_ID,
        GROWTH_CLUSTER_LAYER_ID,
        WHITESPACE_LAYER_ID,
      ];
      map.on("click", (event) => {
        const available = interactiveLayers.filter((id) => map.getLayer(id));
        const feature = map.queryRenderedFeatures(event.point, { layers: available })[0];
        const selectedFeature = feature ? parseSelectedFeature(feature, whitespaceRef.current) : null;
        dispatch({
          type: "select-feature",
          feature: selectedFeature,
        });
        popupRef.current?.remove();
        if (feature && selectedFeature?.kind === "competitor") {
          const competitor = selectedFeature.properties;
          const container = document.createElement("div");
          container.className = "competitor-map-popup";
          const title = document.createElement("strong");
          title.textContent = competitor.competitor_name;
          const address = document.createElement("p");
          address.textContent = competitor.address;
          const tier = document.createElement("p");
          tier.textContent = `${competitor.competitor_tier} competitor`;
          const metrics = document.createElement("p");
          metrics.textContent = `Google rating ${competitor.rating ?? "N/A"} · ${competitor.review_count ?? 0} reviews`;
          const context = document.createElement("p");
          const originId = stateRef.current.competitorOriginBranchId;
          const origin = data.branches.features.find(
            (item) => item.properties.branch_id === originId,
          )?.properties;
          context.textContent = origin
            ? `Selected Bedashing branch: ${origin.branch_name}`
            : "Select a Bedashing branch to inspect catchment relationships.";
          const durations = document.createElement("p");
          durations.textContent = "Loading catchment membership…";
          const observed = document.createElement("p");
          observed.textContent = `${competitor.business_status} · ${competitor.primary_type_display ?? competitor.primary_type ?? "Place type unavailable"}`;
          const source = document.createElement("p");
          source.textContent = `Source: ${competitor.source}`;
          const link = document.createElement("a");
          link.href = String(competitor.google_maps_url);
          link.target = "_blank";
          link.rel = "noreferrer";
          link.textContent = "Open in Google Maps";
          container.append(
            title,
            address,
            tier,
            metrics,
            observed,
            context,
            durations,
            source,
            link,
          );
          const coordinates = (feature.geometry as GeoJSON.Point).coordinates as [number, number];
          popupRef.current = new maplibregl.Popup({ closeButton: true })
            .setLngLat(coordinates)
            .setDOMContent(container)
            .addTo(map);
          Promise.all([
            fetch(
              `${ANALYST_API_URL}/api/competitors/${encodeURIComponent(competitor.competitor_place_id)}`,
            ).then((response) => (response.ok ? response.json() : Promise.reject())),
            fetch(
              `${ANALYST_API_URL}/api/competitors/${encodeURIComponent(competitor.competitor_place_id)}/relationships`,
            ).then((response) => (response.ok ? response.json() : Promise.reject())),
          ])
            .then(
              ([detailPayload, relationshipPayload]: [
                { retrieved_at: string; discovery_categories: string[] },
                {
                  relationships: Array<{ branch_id: string; catchment_durations: number[] }>;
                },
              ]) => {
                const relationship = relationshipPayload.relationships.find(
                  (row) => row.branch_id === originId,
                );
                durations.textContent = relationship
                  ? `Inside ${relationship.catchment_durations.join(", ")} minute catchments`
                  : "No matching catchment relationship for the selected branch.";
                source.textContent = `Source: ${competitor.source} · Retrieved ${detailPayload.retrieved_at} · Discovered via ${detailPayload.discovery_categories.join(", ")}`;
              },
            )
            .catch(() => {
              durations.textContent = "Catchment relationship unavailable.";
            });
        }
      });
      map.on("mousemove", (event) => {
        const available = interactiveLayers.filter((id) => map.getLayer(id));
        map.getCanvas().style.cursor = map.queryRenderedFeatures(event.point, { layers: available })
          .length
          ? "pointer"
          : "";
      });
      setMapReady(true);
    });
    map.on("error", (event) => {
      const message = String(event.error?.message).toLowerCase();
      if (["style", "tile", "fetch", "ajax"].some((term) => message.includes(term))) {
        setTileWarning(true);
      }
    });
    return () => {
      window.clearTimeout(warningTimer);
      map.remove();
      popupRef.current?.remove();
      mapRef.current = null;
    };
  }, [data, dispatch]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    for (const [key, ids] of Object.entries(layerVisibility) as [LayerKey, string[]][]) {
      for (const id of ids) {
        if (map.getLayer(id)) {
          map.setLayoutProperty(id, "visibility", state.visibleLayers[key] ? "visible" : "none");
        }
      }
    }
    map.setFilter(
      BRANCH_LAYER_ID,
      state.branchRecommendations.length === 3 ? null : branchFilter(state),
    );
    map.setFilter(
      DIRECT_COMPETITOR_LAYER_ID,
      state.competitorTiers.includes("DIRECT")
        ? ["==", ["get", "competitor_tier"], "DIRECT"]
        : ["==", 1, 0],
    );
    map.setFilter(
      ADJACENT_COMPETITOR_LAYER_ID,
      state.competitorTiers.includes("ADJACENT")
        ? ["==", ["get", "competitor_tier"], "ADJACENT"]
        : ["==", 1, 0],
    );
    if (map.getLayer(WHITESPACE_LAYER_ID)) {
      map.setFilter(
        WHITESPACE_LAYER_ID,
        state.whitespaceRecommendations.length === 3 ? null : whitespaceFilter(state),
      );
    }
  }, [mapReady, state]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !whitespace) return;
    const source = map.getSource("whitespace") as GeoJSONSource | undefined;
    if (source) source.setData(whitespace);
    else {
      map.addSource("whitespace", { type: "geojson", data: whitespace });
      map.addLayer(whitespaceLayer, CATCHMENT_LAYER_IDS[15]);
      map.setFilter(WHITESPACE_LAYER_ID, whitespaceFilter(stateRef.current));
      map.setLayoutProperty(
        WHITESPACE_LAYER_ID,
        "visibility",
        stateRef.current.visibleLayers.whitespace ? "visible" : "none",
      );
      map.addLayer(selectedWhitespaceLayer);
    }
  }, [mapReady, whitespace]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !map.getLayer(SELECTED_WHITESPACE_LAYER_ID)) return;
    const h3Cell = state.selectedFeature?.kind === "whitespace"
      ? state.selectedFeature.properties.h3_cell
      : "";
    map.setFilter(SELECTED_WHITESPACE_LAYER_ID, ["==", ["get", "h3_cell"], h3Cell]);
  }, [mapReady, state.selectedFeature]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const selected = state.selectedFeature;
    if (selected?.kind === "whitespace") {
      map.flyTo({
        center: [selected.properties.centroid_longitude, selected.properties.centroid_latitude],
        zoom: 11,
        duration: 450,
      });
      return;
    }
    if (selected?.kind === "branch") {
      const feature = data.branches.features.find(
        (row) => row.properties.branch_id === selected.properties.branch_id,
      );
      if (feature) {
        map.flyTo({ center: (feature.geometry as GeoJSON.Point).coordinates as [number, number], zoom: 11, duration: 450 });
        return;
      }
    }
    map.fitBounds(NETWORK_BOUNDS, { padding: 48, duration: 450 });
  }, [data.branches.features, state.mapFitRequest, state.selectedFeature]);

  useEffect(() => {
    const map = mapRef.current;
    const focus = state.relationshipFocus;
    if (!map || !mapReady || !focus) return;
    const branch = data.branches.features.find(
      (feature) => feature.properties.branch_id === focus.branchId,
    );
    const competitor = data.competitors.features.find(
      (feature) => feature.properties.competitor_place_id === focus.competitorId,
    );
    if (!branch || !competitor) return;
    const bounds = new maplibregl.LngLatBounds();
    bounds.extend((branch.geometry as GeoJSON.Point).coordinates as [number, number]);
    bounds.extend((competitor.geometry as GeoJSON.Point).coordinates as [number, number]);
    map.fitBounds(bounds, { padding: 100, duration: 500, maxZoom: 13 });
  }, [data, mapReady, state.relationshipFocus]);

  return (
    <div className="map-stage">
      <div aria-label="Interactive UAE portfolio map" className="map-canvas" ref={containerRef} />
      {!mapReady ? <div className="map-loading">Loading portfolio map…</div> : null}
      {tileWarning ? (
        <div className="tile-warning" role="status">
          Base-map tiles are unavailable. Analytical layers may still load; check your network or
          try again shortly.
        </div>
      ) : null}
    </div>
  );
}
