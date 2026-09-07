"use client";

import { useAgentContext, useFrontendTool } from "@copilotkit/react-core/v2";
import { Bot, Send, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";

import type { DashboardSection } from "@/config/navigation";
import type { CoreDashboardData } from "@/types/app-data";
import type { DashboardAction, DashboardState, LayerKey } from "@/state/dashboard-state";
import { loadWhitespaceOpportunity } from "@/lib/intelligence/api";

const API_URL = process.env.NEXT_PUBLIC_ANALYST_API_URL ?? "http://127.0.0.1:8000";
const recommendation = z.enum(["PROTECT", "HOLD", "SHRINK"]);
const minutes = z.union([z.literal(5), z.literal(10), z.literal(15)]);
const branchTab = z.enum([
  "overview",
  "reviews",
  "services",
  "financial",
  "competition",
  "catchment",
  "decision",
]);
const layer = z.enum([
  "branches",
  "catchment5",
  "catchment10",
  "catchment15",
  "directCompetitors",
  "adjacentCompetitors",
  "whitespace",
  "growthClusters",
  "growthShortlist",
] as [LayerKey, ...LayerKey[]]);
const actionPlanSchema = z.discriminatedUnion("action_name", [
  z.object({
    action_name: z.literal("open_branch_tab"),
    parameters: z.object({ branch_id: z.string().min(1), tab: branchTab }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("select_branch"),
    parameters: z.object({ branch_id: z.string().min(1) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("select_growth_candidate"),
    parameters: z.object({ cluster_id: z.string().min(1) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.enum(["select_whitespace_cell", "zoom_to_whitespace_cell"]),
    parameters: z.object({ h3_cell: z.string().min(1) }),
    reason: z.string().min(1), sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("show_growth_cluster"),
    parameters: z.object({ cluster_id: z.string().min(1) }),
    reason: z.string().min(1), sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("select_branches_for_comparison"),
    parameters: z.object({ branch_ids: z.array(z.string()).min(2).max(4) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("show_ranked_branches"),
    parameters: z.object({ branch_ids: z.array(z.string()).min(1).max(20) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("set_branch_recommendation_filter"),
    parameters: z.object({ recommendations: z.array(recommendation).min(1) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("set_catchment_minutes"),
    parameters: z.object({ minutes }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("set_map_layer_visibility"),
    parameters: z.object({ layer, visible: z.boolean() }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("set_competitor_tier_filter"),
    parameters: z.object({ tiers: z.array(z.enum(["DIRECT", "ADJACENT"])).min(1) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("show_competitor_relationship_on_map"),
    parameters: z.object({
      competitor_id: z.string().min(1),
      branch_id: z.string().min(1),
      travel_minutes: minutes,
    }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("navigate_to_section"),
    parameters: z.object({ section: z.enum(["overview", "performance"]) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("fit_map_to_branch"),
    parameters: z.object({ branch_id: z.string().min(1) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("fit_map_to_branches"),
    parameters: z.object({ branch_ids: z.array(z.string()).min(1).max(20) }),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("fit_map_to_growth_candidates"),
    parameters: z.object({}),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("fit_map_to_network"),
    parameters: z.object({}),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
  z.object({
    action_name: z.literal("reset_dashboard"),
    parameters: z.object({}),
    reason: z.string().min(1),
    sequence: z.number().int().positive(),
  }),
]);

type Message = { role: "user" | "assistant"; content: string };
type AnalystBackend = {
  status: "checking" | "ready" | "unavailable";
  mode: "llm" | "static" | "static-fallback" | null;
};

export function AnalystPanel({
  data,
  state,
  dispatch,
  activeSection,
}: {
  data: CoreDashboardData;
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
  activeSection: DashboardSection;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [backend, setBackend] = useState<AnalystBackend>({ status: "checking", mode: null });
  const router = useRouter();
  const branchCount = data.branches.features.length;
  const context = useMemo(
    () => ({
      active_page: activeSection,
      network_branch_count: branchCount,
      selected_branch:
        state.selectedFeature?.kind === "branch"
          ? state.selectedFeature.properties.branch_id
          : null,
      selected_growth_candidate:
        state.selectedFeature?.kind === "growth-candidate"
          ? state.selectedFeature.properties.cluster_id
          : null,
      selected_whitespace_cell:
        state.selectedFeature?.kind === "whitespace"
          ? state.selectedFeature.properties.h3_cell
          : null,
      compared_branch_ids: state.comparisonBranchIds,
      branch_recommendations: state.branchRecommendations,
      catchment_minutes: state.visibleLayers.catchment10
        ? 10
        : state.visibleLayers.catchment5
          ? 5
          : 15,
      visible_layers: state.visibleLayers,
      competitor_tiers: state.competitorTiers,
      whitespace_filter: state.whitespaceRecommendations,
    }),
    [activeSection, branchCount, state],
  );
  useAgentContext({
    description: "Current Bedashing dashboard state. Use it to target explicit dashboard actions.",
    value: context,
  });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Health check failed (${response.status})`);
        return response.json() as Promise<{ mode?: AnalystBackend["mode"] }>;
      })
      .then((payload) =>
        setBackend({
          status: "ready",
          mode: payload.mode === "llm" ? "llm" : payload.mode ?? "static-fallback",
        }),
      )
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setBackend({ status: "unavailable", mode: null });
      });
    return () => controller.abort();
  }, []);

  useFrontendTool({
    name: "set_branch_recommendation_filter",
    description: "Filter dashboard branches by recommendation.",
    parameters: z.object({ recommendations: z.array(recommendation).min(1) }),
    handler: async ({ recommendations }) => {
      recommendations.forEach((value) => {
        if (!state.branchRecommendations.includes(value))
          dispatch({ type: "toggle-branch-recommendation", value });
      });
      return `Showing ${recommendations.join(", ")} branches`;
    },
  });
  useFrontendTool({
    name: "filter_branch_recommendations",
    description: "Show only requested PROTECT, HOLD, or SHRINK branch recommendations.",
    parameters: z.object({ recommendations: z.array(recommendation).min(1) }),
    handler: async ({ recommendations }) => {
      (["PROTECT", "HOLD", "SHRINK"] as const).forEach((value) => {
        if (state.branchRecommendations.includes(value) !== recommendations.includes(value))
          dispatch({ type: "toggle-branch-recommendation", value });
      });
      return `Branch filter set to ${recommendations.join(", ")}`;
    },
  });
  useFrontendTool({
    name: "set_competitor_tier_filter",
    description: "Filter map competitors to DIRECT, ADJACENT, or both tiers.",
    parameters: z.object({ tiers: z.array(z.enum(["DIRECT", "ADJACENT"])).min(1) }),
    handler: async ({ tiers }) => {
      (["DIRECT", "ADJACENT"] as const).forEach((value) => {
        if (state.competitorTiers.includes(value) !== tiers.includes(value))
          dispatch({ type: "toggle-competitor-tier", value });
      });
      return `Competitor tier filter set to ${tiers.join(", ")}`;
    },
  });
  useFrontendTool({
    name: "filter_whitespace_recommendations",
    description: "Filter whitespace cells to GROW, WATCH, or SKIP recommendations.",
    parameters: z.object({ recommendations: z.array(z.enum(["GROW", "WATCH", "SKIP"])).min(1) }),
    handler: async ({ recommendations }) => {
      (["GROW", "WATCH", "SKIP"] as const).forEach((value) => {
        if (state.whitespaceRecommendations.includes(value) !== recommendations.includes(value))
          dispatch({ type: "toggle-whitespace-recommendation", value });
      });
      return `Whitespace filter set to ${recommendations.join(", ")}`;
    },
  });
  useFrontendTool({
    name: "navigate_to_dashboard_section",
    description: "Navigate to Network Overview or Performance & Health.",
    parameters: z.object({ section: z.enum(["overview", "performance"]) }),
    handler: async ({ section }) => {
      dispatch({ type: "navigate-section", section });
      router.push(section === "performance" ? "/performance" : "/");
      return `Navigated to ${section === "performance" ? "Performance & Health" : "Network Overview"}`;
    },
  });

  async function executePlan(rawPlan: unknown) {
    const parsed = z.array(actionPlanSchema).max(20).safeParse(rawPlan);
    if (!parsed.success) throw new Error("Unsupported or malformed dashboard action");
    const plan = parsed.data;
    for (const item of plan) {
      const p = item.parameters as Record<string, unknown>;
      const ids = p.branch_ids
        ? (p.branch_ids as string[])
        : p.branch_id
          ? [String(p.branch_id)]
          : [];
      if (
        ids.some(
          (id) => !data.branches.features.some((feature) => feature.properties.branch_id === id),
        )
      )
        throw new Error("Action references an unknown branch");
      if (
        p.cluster_id &&
        item.action_name !== "show_growth_cluster" &&
        !data.growthShortlist.features.some(
          (feature) => feature.properties.cluster_id === p.cluster_id,
        )
      )
        throw new Error("Action references an unknown growth candidate");
    }
    const confirmations: string[] = [];
    for (const item of [...plan].sort((a, b) => a.sequence - b.sequence)) {
      const p = item.parameters as { [key: string]: unknown };
      if (item.action_name === "set_branch_recommendation_filter") {
        const values = p.recommendations as DashboardState["branchRecommendations"];
        (["PROTECT", "HOLD", "SHRINK"] as const).forEach((value) => {
          if (state.branchRecommendations.includes(value) !== values.includes(value))
            dispatch({ type: "toggle-branch-recommendation", value });
        });
        confirmations.push(`filtered to ${values.join(", ")} branches`);
      } else if (item.action_name === "select_branch") {
        const branch = data.branches.features.find(
          (feature) => feature.properties.branch_id === String(p.branch_id),
        );
        if (!branch) throw new Error("Unknown branch");
        dispatch({
          type: "select-feature",
          feature: { kind: "branch", properties: branch.properties },
        });
        confirmations.push(`selected ${branch.properties.branch_name}`);
      } else if (item.action_name === "select_whitespace_cell" || item.action_name === "zoom_to_whitespace_cell") {
        const payload = await loadWhitespaceOpportunity(String(p.h3_cell));
        dispatch({ type: "select-feature", feature: { kind: "whitespace", properties: payload.cell } });
        if (item.action_name === "zoom_to_whitespace_cell") dispatch({ type: "fit-network" });
        confirmations.push(`${item.action_name === "select_whitespace_cell" ? "selected" : "focused"} whitespace cell ${String(p.h3_cell)}`);
      } else if (item.action_name === "show_growth_cluster") {
        dispatch({ type: "show-growth-cluster", clusterId: String(p.cluster_id) });
        confirmations.push(`showing growth cluster ${String(p.cluster_id)}`);
      } else if (item.action_name === "open_branch_tab") {
        const branch = data.branches.features.find(
          (feature) => feature.properties.branch_id === String(p.branch_id),
        );
        if (!branch) throw new Error("Unknown branch");
        dispatch({
          type: "select-feature",
          feature: { kind: "branch", properties: branch.properties },
        });
        dispatch({ type: "open-branch-tab", tab: p.tab as DashboardState["branchTab"] });
        confirmations.push(`opened ${String(p.tab)} for ${branch.properties.branch_name}`);
      } else if (item.action_name === "set_catchment_minutes") {
        dispatch({ type: "select-catchment", minutes: p.minutes as 5 | 10 | 15 });
        confirmations.push(`set catchment duration to ${String(p.minutes)} minutes`);
      } else if (item.action_name === "set_competitor_tier_filter") {
        const values = p.tiers as DashboardState["competitorTiers"];
        (["DIRECT", "ADJACENT"] as const).forEach((value) => {
          if (state.competitorTiers.includes(value) !== values.includes(value))
            dispatch({ type: "toggle-competitor-tier", value });
        });
        confirmations.push(`filtered competitors to ${values.join(", ")}`);
      } else if (item.action_name === "set_map_layer_visibility") {
        const key = p.layer as LayerKey;
        if (state.visibleLayers[key] !== p.visible) dispatch({ type: "toggle-layer", layer: key });
        confirmations.push(`${key} layer ${p.visible ? "shown" : "hidden"}`);
      } else if (item.action_name === "show_competitor_relationship_on_map") {
        dispatch({
          type: "show-competitor-relationship",
          competitorId: String(p.competitor_id),
          branchId: String(p.branch_id),
          travelMinutes: p.travel_minutes as 5 | 10 | 15,
        });
        confirmations.push("competitor relationship shown on map");
      } else if (
        item.action_name === "fit_map_to_branch" ||
        item.action_name === "fit_map_to_branches" ||
        item.action_name === "fit_map_to_growth_candidates" ||
        item.action_name === "fit_map_to_network"
      )
        dispatch({ type: "fit-network" });
      else if (item.action_name === "select_branches_for_comparison") {
        dispatch({ type: "set-comparison", branchIds: p.branch_ids as string[] });
        dispatch({ type: "navigate-section", section: "performance" });
        router.push("/performance");
        confirmations.push("comparison panel updated");
      } else if (item.action_name === "show_ranked_branches") {
        dispatch({ type: "set-ranked", branchIds: p.branch_ids as string[] });
        dispatch({ type: "navigate-section", section: "performance" });
        router.push("/performance");
        confirmations.push("ranked overlap results shown");
      } else if (item.action_name === "navigate_to_section") {
        dispatch({ type: "navigate-section", section: p.section as DashboardSection });
        router.push(p.section === "performance" ? "/performance" : "/");
        confirmations.push(
          `navigated to ${p.section === "performance" ? "Performance & Health" : "Network Overview"}`,
        );
      } else if (item.action_name === "reset_dashboard") {
        dispatch({ type: "reset" });
        confirmations.push("dashboard reset");
      }
    }
    return confirmations;
  }
  useFrontendTool({
    name: "select_branch_on_map",
    description: "Select one official branch everywhere in the dashboard.",
    parameters: z.object({ branch_id: z.string().min(1) }),
    handler: async ({ branch_id }) => {
      const branch = data.branches.features.find(
        (feature) => feature.properties.branch_id === branch_id,
      );
      if (!branch) throw new Error("Unknown branch ID");
      dispatch({
        type: "select-feature",
        feature: { kind: "branch", properties: branch.properties },
      });
      return `Selected ${branch.properties.branch_name}`;
    },
    followUp: false,
  });
  useFrontendTool({
    name: "open_branch_tab",
    description: "Select a branch and open a specific shared Branch Details tab.",
    parameters: z.object({ branch_id: z.string().min(1), tab: branchTab }),
    handler: async ({ branch_id, tab }) => {
      const branch = data.branches.features.find(
        (feature) => feature.properties.branch_id === branch_id,
      );
      if (!branch) throw new Error("Unknown branch ID");
      dispatch({
        type: "select-feature",
        feature: { kind: "branch", properties: branch.properties },
      });
      dispatch({ type: "open-branch-tab", tab });
      return `Opened ${tab} for ${branch.properties.branch_name}`;
    },
    followUp: false,
  });
  useFrontendTool({
    name: "set_map_layers",
    description: "Set visibility for one or more map layers.",
    parameters: z.object({ layers: z.array(z.object({ layer, visible: z.boolean() })).min(1) }),
    handler: async ({ layers }) => {
      for (const item of layers)
        if (state.visibleLayers[item.layer] !== item.visible)
          dispatch({ type: "toggle-layer", layer: item.layer });
      return "Map layers updated";
    },
    followUp: false,
  });
  useFrontendTool({
    name: "set_catchment_minutes",
    description: "Set the visible catchment duration.",
    parameters: z.object({ minutes }),
    handler: async ({ minutes: value }) => {
      dispatch({ type: "select-catchment", minutes: value });
      return `Showing the ${value}-minute catchment`;
    },
  });
  useFrontendTool({
    name: "toggle_map_layer",
    description: "Toggle one dashboard map layer.",
    parameters: z.object({ layer, visible: z.boolean() }),
    handler: async ({ layer: key, visible }) => {
      if (state.visibleLayers[key] !== visible) dispatch({ type: "toggle-layer", layer: key });
      return `${key} layer ${visible ? "enabled" : "disabled"}`;
    },
  });
  useFrontendTool({
    name: "reset_dashboard_filters",
    description: "Reset dashboard filters and map layers.",
    parameters: z.object({}),
    handler: async () => {
      dispatch({ type: "reset" });
      return "Dashboard filters reset";
    },
  });
  useFrontendTool({
    name: "select_whitespace_cell",
    description: "Keep the currently selected H3 whitespace cell selected and open its analysis.",
    parameters: z.object({ h3_cell: z.string().min(1) }),
    handler: async ({ h3_cell }) => {
      const payload = await loadWhitespaceOpportunity(h3_cell);
      dispatch({ type: "select-feature", feature: { kind: "whitespace", properties: payload.cell } });
      return `Selected whitespace cell ${h3_cell}`;
    }, followUp: false,
  });
  useFrontendTool({
    name: "zoom_to_whitespace_cell",
    description: "Focus the map on the currently selected whitespace H3 cell.",
    parameters: z.object({ h3_cell: z.string().min(1) }),
    handler: async ({ h3_cell }) => {
      const payload = await loadWhitespaceOpportunity(h3_cell);
      dispatch({ type: "select-feature", feature: { kind: "whitespace", properties: payload.cell } });
      dispatch({ type: "fit-network" }); return `Focused whitespace cell ${h3_cell}`;
    }, followUp: false,
  });
  useFrontendTool({
    name: "show_growth_cluster",
    description: "Show an existing growth cluster related to the selected whitespace cell.",
    parameters: z.object({ cluster_id: z.string().min(1) }),
    handler: async ({ cluster_id }) => {
      dispatch({ type: "show-growth-cluster", clusterId: cluster_id });
      return `Showing growth cluster ${cluster_id}`;
    }, followUp: false,
  });

  async function ask(text: string) {
    const prompt = text.trim();
    if (!prompt || busy) return;
    setQuestion("");
    setMessages((items) => [...items, { role: "user", content: prompt }]);
    setBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/analyst/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: prompt,
          dashboard_context: {
            ...context,
            recent_conversation: messages.slice(-6),
          },
        }),
      });
      if (!response.ok) throw new Error("Analyst unavailable");
      const payload = await response.json();
      const findings = Array.isArray(payload.key_findings)
        ? payload.key_findings.filter((item: unknown) => typeof item === "string")
        : [];
      const uniqueFindings = findings.filter(
        (item: string, index: number) =>
          findings.indexOf(item) === index &&
          !String(payload.answer).toLocaleLowerCase().includes(item.toLocaleLowerCase()),
      );
      let confirmation = "";
      if (Array.isArray(payload.action_plan) && payload.action_plan.length) {
        try {
          const completed = await executePlan(payload.action_plan);
          confirmation = completed.length ? `\n\nActions completed: ${completed.join("; ")}.` : "";
        } catch (error) {
          confirmation = `\n\nActions not completed: ${
            error instanceof Error ? error.message : "invalid dashboard action"
          }.`;
        }
      }
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `${payload.answer}${
            uniqueFindings.length
              ? `\n\n${uniqueFindings.map((item: string) => `• ${item}`).join("\n")}`
              : ""
          }${confirmation}`,
        },
      ]);
    } catch (error) {
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          content: `The analyst backend is unavailable${
            error instanceof Error ? `: ${error.message}` : ""
          }. Start FastAPI on port 8000, then retry.`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        className="analyst-launcher"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <Bot size={18} /> AI Portfolio Analyst
      </button>
      {open ? (
        <aside className="analyst-panel" aria-label="AI Portfolio Analyst">
          <header>
            <div>
              <span className="eyebrow">Grounded assistant</span>
              <h2>Portfolio Analyst</h2>
              <span className={`analyst-mode ${backend.status}`}>
                {backend.status === "checking"
                  ? "Checking agent…"
                  : backend.status === "unavailable"
                    ? "Agent offline"
                    : backend.mode === "llm"
                      ? "AI agent online"
                      : "Static fallback — no AI model"}
              </span>
            </div>
            <button
              className="icon-button"
              onClick={() => setOpen(false)}
              aria-label="Close analyst"
            >
              <X size={16} />
            </button>
          </header>
          <div className="analyst-messages">
            {messages.length === 0 ? (
              <div className="analyst-starters">
                <p>
                  {backend.mode === "llm"
                    ? "Ask naturally—the agent can query validated data and operate the dashboard."
                    : backend.status === "unavailable"
                      ? "Start the API to connect the portfolio agent."
                      : "Ask about the validated portfolio snapshot."}
                </p>
                {[
                  "Which branches should leadership review first?",
                  "Show branches with the highest overlap.",
                  "Show the reviewed growth candidates.",
                ].map((item) => (
                  <button key={item} onClick={() => ask(item)}>
                    {item}
                  </button>
                ))}
              </div>
            ) : (
              messages.map((item, index) => (
                <div key={index} className={`analyst-message ${item.role}`}>
                  <strong>{item.role === "user" ? "You" : "Analyst"}</strong>
                  <p className="preserve-lines">{item.content}</p>
                </div>
              ))
            )}
            {busy ? <div className="analyst-status">Querying validated app_data…</div> : null}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void ask(question);
            }}
            className="analyst-input"
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about branches, overlap or growth…"
              aria-label="Ask analyst"
            />
            <button type="submit" aria-label="Send question">
              <Send size={16} />
            </button>
          </form>
          <small>Answers are grounded in app_data. No scores or recommendations are changed.</small>
        </aside>
      ) : null}
    </>
  );
}
