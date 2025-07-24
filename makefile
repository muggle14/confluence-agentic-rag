# Makefile for Azure Functions Docker Operations
# Usage: make [target]

# Variables
IMAGE_NAME := confluence-qa-functions
CONTAINER_NAME := confluence-qa-dev
REGISTRY := $(or $(DOCKER_REGISTRY),localhost:5000)
VERSION := $(or $(VERSION),latest)
PORT := 7071

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

.PHONY: help build run stop logs shell clean push prod test lint

# Default target
help:
	@echo "$(GREEN)Azure Functions Docker Management$(NC)"
	@echo ""
	@echo "Available targets:"
	@echo "  $(YELLOW)make build$(NC)    - Build Docker image"
	@echo "  $(YELLOW)make run$(NC)      - Run locally with docker-compose"
	@echo "  $(YELLOW)make stop$(NC)     - Stop all containers"
	@echo "  $(YELLOW)make logs$(NC)     - View container logs"
	@echo "  $(YELLOW)make shell$(NC)    - Open shell in container"
	@echo "  $(YELLOW)make clean$(NC)    - Clean up containers and volumes"
	@echo "  $(YELLOW)make push$(NC)     - Push image to registry"
	@echo "  $(YELLOW)make prod$(NC)     - Build production image"
	@echo "  $(YELLOW)make test$(NC)     - Run tests in container"
	@echo "  $(YELLOW)make lint$(NC)     - Run code linting"
	@echo ""
	@echo "Variables:"
	@echo "  REGISTRY=$(REGISTRY)"
	@echo "  VERSION=$(VERSION)"

# Build Docker image
build:
	@echo "$(YELLOW)Building Docker image...$(NC)"
	@docker build -t $(IMAGE_NAME):$(VERSION) .
	@echo "$(GREEN)✅ Image built: $(IMAGE_NAME):$(VERSION)$(NC)"

# Run locally with docker-compose
run: check-env
	@echo "$(YELLOW)Starting local development environment...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)✅ Azure Functions running at http://localhost:$(PORT)$(NC)"
	@echo "$(GREEN)✅ Azurite running at http://localhost:10000$(NC)"

# Stop all containers
stop:
	@echo "$(YELLOW)Stopping containers...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✅ Containers stopped$(NC)"

# View logs
logs:
	@docker-compose logs -f functions

# Open shell in container
shell:
	@docker exec -it $(CONTAINER_NAME) /bin/bash

# Clean up everything
clean:
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@docker-compose down -v
	@docker system prune -f
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

# Push to registry
push: build
	@echo "$(YELLOW)Pushing image to registry...$(NC)"
	@docker tag $(IMAGE_NAME):$(VERSION) $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	@docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	@echo "$(GREEN)✅ Pushed to $(REGISTRY)/$(IMAGE_NAME):$(VERSION)$(NC)"

# Build production image
prod:
	@echo "$(YELLOW)Building production image...$(NC)"
	@docker build \
		--build-arg BUILD_DATE=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ") \
		--build-arg VERSION=$(VERSION) \
		-f Dockerfile.production \
		-t $(IMAGE_NAME):$(VERSION)-prod .
	@echo "$(GREEN)✅ Production image built$(NC)"

# Run tests in container
test: build
	@echo "$(YELLOW)Running tests...$(NC)"
	@docker run --rm \
		-v $(PWD)/tests:/home/site/wwwroot/tests \
		$(IMAGE_NAME):$(VERSION) \
		python -m pytest tests/
	@echo "$(GREEN)✅ Tests completed$(NC)"

# Run linting
lint:
	@echo "$(YELLOW)Running code linting...$(NC)"
	@docker run --rm \
		-v $(PWD):/home/site/wwwroot \
		$(IMAGE_NAME):$(VERSION) \
		python -m pylint api_service.py confluence_qa_orchestrator.py
	@echo "$(GREEN)✅ Linting completed$(NC)"

# Check if .env file exists
check-env:
	@if [ ! -f .env ]; then \
		echo "$(RED)❌ .env file not found$(NC)"; \
		echo "$(YELLOW)Creating .env from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(GREEN)✅ Created .env file. Please update it with your values.$(NC)"; \
		exit 1; \
	fi

# Development workflow shortcuts
dev: build run logs

restart: stop run

# Azure deployment helpers
deploy-aci:
	@echo "$(YELLOW)Deploying to Azure Container Instances...$(NC)"
	az container create \
		--resource-group $(RESOURCE_GROUP) \
		--name $(CONTAINER_NAME)-aci \
		--image $(REGISTRY)/$(IMAGE_NAME):$(VERSION) \
		--cpu 2 --memory 4 \
		--ports 80 \
		--environment-variables-file .env.production

deploy-functions:
	@echo "$(YELLOW)Deploying to Azure Functions...$(NC)"
	func azure functionapp publish $(FUNCTION_APP_NAME) --docker

# Docker compose shortcuts
up:
	@docker-compose up -d

down:
	@docker-compose down

ps:
	@docker-compose ps

# Monitoring
monitor:
	@echo "$(YELLOW)Opening monitoring dashboard...$(NC)"
	@docker-compose logs -f --tail=100 functions

health:
	@echo "$(YELLOW)Checking health...$(NC)"
	@curl -f http://localhost:$(PORT)/api/health || echo "$(RED)❌ Health check failed$(NC)"