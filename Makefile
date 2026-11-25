# GPUGuard Makefile
.PHONY: help install test lint format typecheck clean build run-mock run-prod docs

# Default target
help:
	@echo "GPUGuard - AI-powered GPU observability for ROS 2"
	@echo ""
	@echo "Targets:"
	@echo "  install      - Install package in development mode"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-int     - Run integration tests only"
	@echo "  lint         - Run ruff linter"
	@echo "  format       - Format code with ruff and black"
	@echo "  typecheck    - Run mypy type checker"
	@echo "  pre-commit   - Run pre-commit hooks"
	@echo "  run-mock     - Run full demo with mock collector"
	@echo "  run-prod     - Run production mode (requires GPU)"
	@echo "  run-ros2     - Run via ROS 2 launch"
	@echo "  build-ros2   - Build ROS 2 package"
	@echo "  docs         - Build documentation"
	@echo "  clean        - Clean build artifacts"

# Installation
install:
	pip install -e .[dev]
	pre-commit install

install-ros2:
	mkdir -p ~/ros2_ws/src
	ln -sf $(CURDIR)/src/gpuguard/ros2 ~/ros2_ws/src/gpuguard_ros2
	cd ~/ros2_ws && rosdep install --from-paths src --ignore-src -r -y
	cd ~/ros2_ws && colcon build --packages-select gpuguard_ros2 --event-handlers console_direct+

# Testing
test:
	pytest

test-unit:
	pytest tests/unit -v

test-int:
	pytest tests/integration -v

test-cov:
	pytest --cov=gpuguard --cov-report=html --cov-report=term

# Linting & Formatting
lint:
	ruff check src tests

format:
	ruff check --fix src tests
	black src tests

typecheck:
	mypy src/gpuguard

pre-commit:
	pre-commit run --all-files

# Running
run-mock:
	gpuguard-run mock --log-level INFO

run-prod:
	gpuguard-run prod --log-level INFO

run-ros2:
	gpuguard-run ros2 --log-level INFO

run-collector:
	gpuguard-collector --mock --log-level DEBUG

run-monitor:
	gpuguard-ros-monitor --log-level DEBUG

run-api:
	gpuguard-api --log-level DEBUG

run-dashboard:
	gpuguard-dashboard --log-level DEBUG

# Build
build:
	python -m build

build-ros2:
	cd ~/ros2_ws && colcon build --packages-select gpuguard_ros2 --event-handlers console_direct+

# Documentation
docs:
	cd docs && mkdocs build

docs-serve:
	cd docs && mkdocs serve

# Clean
clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf htmlcov/ .coverage
	rm -rf artifacts/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Development
dev-setup: install install-ros2 pre-commit

demo-yolo:
	gpuguard-demo --model yolov8n --device cuda --batch 4 --duration 30

demo-stress:
	python scripts/demo_gpu_stress.py --compute 1.0 --memory 6 --duration 60

benchmark:
	gpuguard-benchmark --duration 10 --output artifacts/benchmark_results.json

# Docker (when available)
docker-build:
	docker build -t gpuguard:latest .

docker-run:
	docker run --gpus all --net=host -it gpuguard:latest

# CI helpers
ci-test: lint typecheck test

ci-build: clean build