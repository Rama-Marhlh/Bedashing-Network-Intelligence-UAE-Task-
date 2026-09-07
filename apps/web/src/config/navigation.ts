export const NAVIGATION_ITEMS = [
  { href: "/", label: "Network Overview", key: "overview" },
  { href: "/performance", label: "Performance & Health", key: "performance" },
] as const;

export type DashboardSection = (typeof NAVIGATION_ITEMS)[number]["key"];
