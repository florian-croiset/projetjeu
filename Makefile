.PHONY: all install run server relay test lint bench fps build build-dev build-clean clean

all: run

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

run:
	python3 main.py

# Headless dedicated server (no window): python3 -m net.dedicated --help
server:
	python3 -m net.dedicated

# Public relay for room-code play
relay:
	python3 -m net.relay_server

test:
	python3 -m pytest

lint:
	python3 -m ruff check .

bench:
	python3 tools/benchmark.py

fps:
	python3 tools/fps_benchmark.py

build:
	./packaging/build_linux.sh

build-dev:
	./packaging/build_linux.sh --dev

build-clean:
	./packaging/build_linux.sh --clean

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null; \
	rm -rf build/ dist/ .pytest_cache .ruff_cache
