# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

# Dependencies zuerst für Layer-Caching
COPY package.json ./
RUN npm install

# Rest der Sources und Build
COPY . .
RUN npm run build

# ---------- Serve stage ----------
FROM nginx:1.27-alpine

# Custom nginx config mit /api + /ws Proxy zum Backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
