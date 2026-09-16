.PHONY: help fmt fmt-check check test build validate

help:
	@echo perfeng-analysis engineering command surface
	@echo "  make fmt        Format Python sources"
	@echo "  make fmt-check  Verify formatting without changes"
	@echo "  make check      Run formatting, linting and type checks"
	@echo "  make test       Run the unit-test suite"
	@echo "  make build      Build source and wheel distributions"
	@echo "  make validate   Run all portable non-image checks"

fmt:
	uv run --locked ruff format .

fmt-check:
	uv run --locked ruff format --check .

check: fmt-check
	uv run --locked ruff check .
	uv run --locked ty check

test:
	uv run --locked python -m unittest discover -s tests -v

build:
	uv build

validate: check test build
