FROM node:18-alpine AS builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build

FROM nginx:1.27-alpine
RUN addgroup -S app && adduser -S -G app app
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /build/dist /usr/share/nginx/html
RUN chown -R app:app /usr/share/nginx/html /var/cache/nginx /var/run /var/log/nginx
USER app
EXPOSE 8080
CMD ["nginx","-g","daemon off;"]
