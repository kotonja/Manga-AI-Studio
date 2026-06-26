FROM node:22-alpine AS base

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared/package.json ./packages/shared/package.json

FROM base AS dev
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
COPY packages/shared ./packages/shared
EXPOSE 3000
CMD ["pnpm", "--filter", "@manga-ai/web", "dev", "--hostname", "0.0.0.0"]

FROM base AS deps
RUN pnpm install --frozen-lockfile

FROM deps AS builder
ENV NEXT_OUTPUT_STANDALONE=true
COPY apps/web ./apps/web
COPY packages/shared ./packages/shared
RUN pnpm --filter @manga-ai/web build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup -S nextjs && adduser -S nextjs -G nextjs

COPY --from=builder --chown=nextjs:nextjs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
