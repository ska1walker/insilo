"use client";

import { useEffect } from "react";
import { fangeInstallAngebot } from "@/lib/installation";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    // Vor allem anderen: das Angebot zum Installieren kommt nur einmal.
    fangeInstallAngebot();
    if (!("serviceWorker" in navigator)) return;

    // Only register in production builds; under `next dev` the SW serves
    // stale chunks and confuses HMR.
    if (process.env.NODE_ENV !== "production") return;

    const handle = window.setTimeout(() => {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch((err) => console.warn("SW registration failed:", err));
    }, 1500);

    return () => window.clearTimeout(handle);
  }, []);

  return null;
}
