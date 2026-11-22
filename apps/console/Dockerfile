ARG VITE_API_URL=/api/v1

FROM node:22-alpine AS build
WORKDIR /srv/console
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci
COPY apps/console ./
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /srv/console/dist /usr/share/nginx/html
COPY apps/console/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 4173
