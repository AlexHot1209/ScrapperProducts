FROM node:20-alpine AS deps
WORKDIR /workspace
COPY package.json /workspace/package.json
COPY frontend/package.json /workspace/frontend/package.json
COPY backend/packages/shared/types/package.json /workspace/backend/packages/shared/types/package.json
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /workspace
COPY --from=deps /workspace/node_modules /workspace/node_modules
COPY . .
RUN npm --workspace frontend run build

FROM node:20-alpine AS runner
WORKDIR /workspace
ENV NODE_ENV=production
COPY --from=builder /workspace/frontend/.next /workspace/frontend/.next
COPY --from=builder /workspace/frontend/public /workspace/frontend/public
COPY --from=builder /workspace/frontend/package.json /workspace/frontend/package.json
COPY --from=deps /workspace/node_modules /workspace/node_modules
EXPOSE 3000
CMD ["npm", "--workspace", "frontend", "run", "start"]
