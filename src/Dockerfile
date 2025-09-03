# Stage 1: Build React app
FROM node:18-alpine AS build

WORKDIR /app

# Copy only package.json and package-lock.json first
COPY package*.json ./

RUN npm install

# Copy the rest of the frontend source code
COPY . .

RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
