"use client";

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
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
