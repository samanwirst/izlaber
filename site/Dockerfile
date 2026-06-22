FROM node:22-slim AS deps

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/site
COPY site/package.json site/package-lock.json* ./
RUN npm install

FROM node:22-slim AS builder

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/site
COPY --from=deps /app/site/node_modules ./node_modules
COPY site ./
RUN npm run build

FROM node:22-slim AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/site
COPY --from=builder /app/site/.next/standalone ./
COPY --from=builder /app/site/.next/static ./.next/static
COPY --from=builder /app/site/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
