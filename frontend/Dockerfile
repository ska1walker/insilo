# syntax=docker/dockerfile:1.7
# ===========================================================================
# Insilo Frontend (Next.js 15 PWA)
#
# Multi-Stage-Build für minimales Final-Image.
# Läuft als non-root (UID 1000) — Olares-konform.
# ===========================================================================

# ---- Stage 1: Dependencies -------------------------------------------------
# Install ALL dependencies (including dev) — tailwind, postcss, typescript
# are dev deps but the production build needs them.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- Stage 2: Build --------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=https://insilo-api.placeholder/api
ENV NEXT_PUBLIC_USER=placeholder
RUN npm run build

# ---- Stage 3: Runner -------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root User anlegen (UID 1000 — entspricht runAsUser in OlaresManifest).
# node:alpine ships with a "node" user on UID 1000, so we rename instead of
# adding a second user with the same UID.
RUN deluser node 2>/dev/null || true && \
    addgroup -g 1000 -S insilo && \
    adduser -S insilo -u 1000 -G insilo

# Standalone-Build kopieren (next.config.mjs output: "standalone")
COPY --from=builder --chown=insilo:insilo /app/.next/standalone ./
COPY --from=builder --chown=insilo:insilo /app/.next/static ./.next/static
COPY --from=builder --chown=insilo:insilo /app/public ./public

USER insilo

EXPOSE 3000

# Liveness: the Next.js server answers at /; full health is enforced by
# Kubernetes/Olares readinessProbe + the backend's own /health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD wget --quiet --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
