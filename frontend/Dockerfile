# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

# Dependencies first for layer caching
COPY package.json ./
RUN npm install

# Remaining sources and build
COPY . .
RUN npm run build

# ---------- Serve stage ----------
FROM nginx:1.27-alpine

# Custom nginx config with /api + /ws proxy to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i '1s/^\xEF\xBB\xBF//' /etc/nginx/conf.d/default.conf

# Built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

