# syntax=docker/dockerfile:1.7

# ---------- Build stage ----------
# Bun is used because the project is locked via bun.lock (see apps/web/README.md).
FROM oven/bun:1.3-alpine AS build

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy the rest of the source after dependencies are cached.
COPY . .

# Optional API base URL baked into the SPA bundle. Defaults to the relative
# "/api/v1" path so the runtime Nginx reverse proxy can forward to the API
# service. Override at build time when the API lives on a different origin:
#   docker build --build-arg VITE_API_BASE_URL=https://api.example.com/api/v1 .
#
# NOTE: the default MUST be set on the ARG (not just relied on via api.ts'
# `?? '/api/v1'` fallback). An unset build-arg would otherwise produce an
# empty `ENV VITE_API_BASE_URL=""`, and `??` does not fall back on empty
# strings — that bakes a broken `API_BASE = ""` into the bundle.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# `build-only` runs `vite build` without type-check. Type-check is part of the
# local/CI pipeline (see AGENTS.md > Common Commands) and is intentionally
# skipped here to keep image builds fast and avoid `vue-tsc` memory pressure.
RUN bun run build-only

# ---------- Runtime stage ----------
FROM nginx:1.27-alpine AS runtime

# Upstream the SPA's `/api/` requests are forwarded to. Override at container
# start when wiring this image to a different API endpoint, e.g.:
#   docker run -e API_UPSTREAM=http://api:18000 ...
ENV API_UPSTREAM=http://api:18000

# nginx:alpine renders /etc/nginx/templates/*.template via envsubst on boot.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Default CMD/ENTRYPOINT from the base image already runs nginx in the
# foreground after rendering templates.
