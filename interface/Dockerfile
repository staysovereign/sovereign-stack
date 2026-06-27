# Build stage
# Build context is the repo root (see docker-compose interface.build.context)
# so this Dockerfile can reach both interface/ and nginx/.
FROM node:22-alpine AS builder
WORKDIR /app
COPY interface/package.json ./
RUN npm install
COPY interface/ .
RUN npm run build

# Serve stage — Nginx delivers the static bundle
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx/sovereign.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
