import type {
  BranchIntelligence,
  CompetitorDetailsData,
  CompetitorRelationshipsData,
  ReviewPage,
  ServiceVariant,
  ServiceCategorySummary,
  PortfolioHealthData,
  WhitespaceOpportunityAnalysis,
} from "@/types/intelligence";

const API_URL = process.env.NEXT_PUBLIC_ANALYST_API_URL ?? "http://127.0.0.1:8000";

async function apiJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Intelligence request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export const loadBranchIntelligence = (branchId: string, signal?: AbortSignal) =>
  apiJson<BranchIntelligence>(`/api/branches/${encodeURIComponent(branchId)}/intelligence`, signal);

export interface ReviewFilters {
  query: string;
  sentiment: string;
  stars: string;
  language: string;
  topic: string;
  date_from: string;
  date_to: string;
  page: number;
  sort: "newest" | "oldest";
}

export function loadBranchReviews(branchId: string, filters: ReviewFilters, signal?: AbortSignal) {
  const query = new URLSearchParams({
    page: String(filters.page),
    page_size: "20",
    sort: filters.sort,
  });
  for (const key of [
    "query",
    "sentiment",
    "stars",
    "language",
    "topic",
    "date_from",
    "date_to",
  ] as const) {
    if (filters[key]) query.set(key, String(filters[key]));
  }
  return apiJson<ReviewPage>(
    `/api/branches/${encodeURIComponent(branchId)}/reviews?${query}`,
    signal,
  );
}

export const loadServices = (signal?: AbortSignal) =>
  apiJson<{
    items: ServiceVariant[];
    category_summaries: ServiceCategorySummary[];
    availability: string;
  }>("/api/services", signal);

export const loadCompetitorDetails = (competitorId: string, signal?: AbortSignal) =>
  apiJson<CompetitorDetailsData>(`/api/competitors/${encodeURIComponent(competitorId)}`, signal);

export const loadCompetitorRelationships = (competitorId: string, signal?: AbortSignal) =>
  apiJson<CompetitorRelationshipsData>(
    `/api/competitors/${encodeURIComponent(competitorId)}/relationships`,
    signal,
  );

export const loadPortfolioHealth = (signal?: AbortSignal) =>
  apiJson<PortfolioHealthData>("/api/portfolio-health", signal);

export const loadWhitespaceOpportunity = (h3Cell: string, signal?: AbortSignal) =>
  apiJson<WhitespaceOpportunityAnalysis>(`/api/whitespace/${encodeURIComponent(h3Cell)}`, signal);
