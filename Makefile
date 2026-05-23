.PHONY: all install run relay build build-dev build-clean clean

all: run

run:
	python3 main.py

install:
	pip install -r requirements.txt

relay:
	python3 -m reseau.relay_server

build:
	./build_linux.sh

build-dev:
	./build_linux.sh --dev

build-clean:
	./build_linux.sh --clean

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
	rm -rf build/ dist/ *.spec

