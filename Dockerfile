FROM ruby:3.4-alpine

RUN apk add --no-cache \
    build-base \
    nodejs

WORKDIR /usr/src/app

COPY Gemfile ./

RUN gem install bundler:2.3.26 && \
    bundle config set --local path 'vendor/bundle' && \
    bundle install --jobs 4 --retry 3

CMD ["jekyll", "serve", "-H", "0.0.0.0", "-w", "--config", "_config.yml,_config_docker.yml"]