# Build args
ARG VITE_API_URL=https://flc-bank-api.fly.dev

# Frontend Dockerfile - Grafeno Portal
FROM node:20-alpine AS build

# Receber build arg
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

WORKDIR /app

# Copiar package files
COPY package*.json ./

# Instalar dependências
RUN npm ci

# Copiar código fonte
COPY . .

# Build da aplicação
RUN npm run build

# Stage de produção com nginx
FROM nginx:alpine

# Copiar build para nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copiar configuração nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
