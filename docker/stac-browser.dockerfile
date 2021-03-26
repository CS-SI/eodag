# build stage
FROM node:lts-jessie-slim as build-stage

# install git
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y git

#clone repository
RUN git clone https://github.com/radiantearth/stac-browser.git

# move to folder
WORKDIR /stac-browser

# install
RUN npm install

# start application
RUN CATALOG_URL=http://localhost:5000 npm run build

# production stage, self describing
FROM nginx:stable-alpine as production-stage

COPY --from=build-stage /stac-browser/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
