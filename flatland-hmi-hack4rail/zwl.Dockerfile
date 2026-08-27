# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Build arg: URL of the Flask Railway brain reachable from the BROWSER
# Local dev:  http://localhost:5001
# Deployment: http://<server-ip>:5001  or  https://railway.yourdomain.com
ARG RAILWAY_SIMU_URL=http://localhost:5001

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

# Replace hardcoded localhost:5001 with the configured URL
RUN find /app/src -name "*.ts" \
    -exec sed -i "s|http://localhost:5001|${RAILWAY_SIMU_URL}|g" {} \;

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/dist/frontend /usr/share/nginx/html

# Simple nginx config — no proxy needed since URL is baked in
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  index index.html; \
  location / { try_files $uri $uri/ /index.html; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
