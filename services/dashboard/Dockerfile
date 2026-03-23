# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy transcript-rendering built package
COPY transcript-rendering/package.json /transcript-rendering/package.json
COPY transcript-rendering/dist/ /transcript-rendering/dist/

# Install dependencies
# Pack transcript-rendering so npm ci can resolve the file: dependency
RUN cd /transcript-rendering && npm pack --pack-destination /tmp/
COPY dashboard/package*.json ./
RUN npm ci
# Physical copy over the symlink so Turbopack can resolve it
RUN rm -rf node_modules/@vexaai/transcript-rendering && \
    cp -r /transcript-rendering node_modules/@vexaai/transcript-rendering

# Copy source code
COPY dashboard/src ./src
COPY dashboard/public ./public
COPY dashboard/next.config.ts dashboard/tsconfig.json dashboard/postcss.config.mjs dashboard/eslint.config.mjs ./
COPY dashboard/components.json ./

# Build application
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
