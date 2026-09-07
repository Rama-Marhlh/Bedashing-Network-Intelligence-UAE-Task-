import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LayerControls } from "@/components/map/layer-controls";
import { createInitialDashboardState } from "@/state/dashboard-state";

describe("layer controls", () => {
  it("exposes keyboard-accessible switches and dispatches changes", () => {
    const dispatch = vi.fn();
    render(
      <LayerControls
        dispatch={dispatch}
        state={createInitialDashboardState("overview")}
        whitespaceLoading={false}
      />,
    );

    const switchControl = screen.getByRole("switch", { name: "Toggle Whitespace opportunities" });
    fireEvent.click(switchControl);

    expect(dispatch).toHaveBeenCalledWith({ type: "toggle-layer", layer: "whitespace" });
    expect(screen.getByRole("button", { name: "15 min" })).toHaveAttribute("aria-pressed", "false");
  });
});
