/**
 * Liveness/readiness endpoint used by the Olares readinessProbe.
 * Returns 200 OK as long as the Next.js server can render. No deeper
 * health checks (backend reachability etc.) — those probes live on the
 * backend itself at /health/* on port 8000.
 */
export function GET(): Response {
  return Response.json({ status: "ok", service: "insilo-frontend" });
}
