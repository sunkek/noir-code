SHELL := /bin/bash

# NoiR Code is a stateless 3-service stack (imaging sidecar + Go gateway + SPA);
# no database/broker, so the targets are just: run the stack, dev on host, docs.
COMPOSE := docker compose -f deploy/docker-compose.yml

.PHONY: help up down restart logs ps build run-local gen-api-docs

help:
	@echo "Targets:"
	@echo "  make up           - Build + start the full stack (http://localhost:8080)"
	@echo "  make down         - Stop and remove containers"
	@echo "  make restart      - down then up"
	@echo "  make build        - Build images without starting"
	@echo "  make logs         - Follow container logs"
	@echo "  make ps           - Show container status"
	@echo "  make run-local    - Run sidecar + gateway + vite on the host (no Docker)"
	@echo "  make gen-api-docs - Regenerate the OpenAPI 3.1 spec (swaggo v2)"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: down up

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

# Host dev loop: Python imaging sidecar (8001), Go gateway (8000), vite (5173).
# Ctrl-C tears all three down.
run-local:
	@set -e; \
	trap 'kill 0' EXIT; \
	( cd service/python && NOIRCODE_API_PORT=8001 uv run noir-api ) & \
	( cd service/backend && NOIRCODE_API_FIBER_PORT=8000 \
		NOIRCODE_API_IMAGING_BASE_URL=http://localhost:8001 \
		NOIRCODE_API_FIBER_SWAGGER_FILE_PATH=docs/swagger.json \
		go run ./cmd/main ) & \
	( cd service/frontend && npm run dev ); \
	wait

# Regenerate OpenAPI 3.1 docs with swaggo v2 (emits 3.1 via --v3.1).
# Install once: go install github.com/swaggo/swag/v2/cmd/swag@latest
gen-api-docs:
	cd ./service/backend && \
	swag fmt -d ./cmd/main && \
	swag init -d ./cmd/main -o ./docs --v3.1 --parseInternal --parseDependency --parseDependencyLevel=1
