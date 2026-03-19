# Stage 1: Build the React frontend
# REGISTRY_PREFIX: empty for Docker Hub, or university harbor cache.
ARG REGISTRY_PREFIX=harbor.pg.innopolis.university/docker-hub-cache/
FROM ${REGISTRY_PREFIX}node:25-alpine AS builder

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build


# Stage 2: Serve with Caddy
ARG REGISTRY_PREFIX=harbor.pg.innopolis.university/docker-hub-cache/
FROM ${REGISTRY_PREFIX}caddy:2.11-alpine

COPY --from=builder /app/dist /srv