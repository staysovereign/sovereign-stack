# Build stage
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Serve stage — Nginx delivers the static bundle
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY ../nginx/sovereign.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
