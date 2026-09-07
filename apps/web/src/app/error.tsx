"use client";

import { useEffect } from "react";

const RECOVERY_KEY = "bedashing-dashboard-render-recovery";

export default function ErrorPage({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    if (sessionStorage.getItem(RECOVERY_KEY)) return;
    sessionStorage.setItem(RECOVERY_KEY, error.digest ?? error.name ?? "render-error");
    window.location.reload();
  }, [error]);

  const retry = () => {
    sessionStorage.removeItem(RECOVERY_KEY);
    window.location.reload();
  };

  return (
    <main className="full-state error-state">
      <h1>Dashboard unavailable</h1>
      <p>The static application could not be rendered.</p>
      <button className="button" onClick={retry}>
        Try again
      </button>
    </main>
  );
}
