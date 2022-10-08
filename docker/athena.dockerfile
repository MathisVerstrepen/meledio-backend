FROM node:18-alpine

WORKDIR /athena

COPY ./athena/package.json /athena/package.json

RUN yarn install

COPY ./athena /athena

CMD ["yarn", "dev"]