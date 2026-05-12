# syntax=docker/dockerfile:1.7
# ===========================================================================
# Insilo Frontend (Next.js 15 PWA)
#
# Multi-Stage-Build für minimales Final-Image.
# Läuft als non-root (UID 1000) — Olares-konform.
# ===========================================================================

# ---- Stage 1: Dependencies -------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ---- Stage 2: Build --------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- Stage 3: Runner -------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root User anlegen (UID 1000 — entspricht runAsUser in OlaresManifest)
RUN addgroup -g 1000 -S insilo && \
    adduser -S insilo -u 1000 -G insilo

# Standalone-Build kopieren (next.config.mjs output: "standalone")
COPY --from=builder --chown=insilo:insilo /app/.next/standalone ./
COPY --from=builder --chown=insilo:insilo /app/.next/static ./.next/static
COPY --from=builder --chown=insilo:insilo /app/public ./public

USER insilo

EXPOSE 3000

# Health-Endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD wget --quiet --spider http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
