#!/usr/bin/env bash
# Quick shortcut to get a shell inside the staging API container

docker compose -f ./generated/docker-compose.staging.yml \
  --env-file .env.staging \
  exec api /bin/bash
