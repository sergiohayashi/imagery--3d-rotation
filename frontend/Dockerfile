# Stage 1 - the build process
FROM node:16 as build-deps
WORKDIR /usr/src/app

# value comes from --build-arg
ARG REACT_APP_VERSION
ENV REACT_APP_VERSION=$REACT_APP_VERSION
RUN echo ">>> Building React app with REACT_APP_VERSION=${REACT_APP_VERSION}"

# Increase Node's memory limit to 4GB
ENV NODE_OPTIONS="--max_old_space_size=4096"

COPY package*.json ./
RUN npm install
COPY . ./
RUN npm run build

# Stage 2 - the production environment
FROM nginx:1.12-alpine
COPY --from=build-deps /usr/src/app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


