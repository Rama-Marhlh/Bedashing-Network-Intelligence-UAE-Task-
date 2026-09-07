import type { Metadata } from "next";

import "@/styles/globals.css";
import { CopilotProvider } from "@/components/copilot/copilot-provider";
import { DashboardStateProvider } from "@/state/dashboard-state-provider";

export const metadata: Metadata = {
  title: "Bedashing Network Intelligence",
  description: "AI-Enabled Geospatial Decision Support for Retail Network Right-Sizing",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <CopilotProvider>
          <DashboardStateProvider>{children}</DashboardStateProvider>
        </CopilotProvider>
      </body>
    </html>
  );
}
