UV_RUN := uv run --locked --offline

.PHONY: help bootstrap doctor fmt fmt-check docs-check check test build verify vuln supply-chain validate

help:
	@echo perfeng-analysis engineering command surface
	@echo "  make bootstrap  Resolve locked Python dependencies"
	@echo "  make doctor     Report the effective local toolchain"
	@echo "  make fmt        Format Python sources"
	@echo "  make fmt-check  Verify formatting without changes"
	@echo "  make docs-check Verify repository documentation and policy"
	@echo "  make check      Run formatting, policy, lock, lint and type checks"
	@echo "  make test       Run the unit-test suite"
	@echo "  make build      Build source and wheel distributions"
	@echo "  make verify     Run the offline development feedback loop"
	@echo "  make vuln       Audit locked dependencies for supported platforms"
	@echo "  make supply-chain  Run automated dependency-risk checks"
	@echo "  make validate   Run all portable non-image acceptance checks"

bootstrap:
	uv sync --locked

doctor:
	@git --version
	@uv --version
	@$(UV_RUN) python --version
	@$(MAKE) --version

fmt:
	$(UV_RUN) ruff format .

fmt-check:
	$(UV_RUN) ruff format --check .

docs-check:
	$(UV_RUN) python scripts/repo_check.py

check: fmt-check docs-check
	uv lock --check --offline
	$(UV_RUN) ruff check .
	$(UV_RUN) ty check

test:
	$(UV_RUN) python -m unittest discover -s tests -v

build:
	uv build --offline

verify: check test build

vuln:
	uv audit --preview-features audit-command --locked --python-platform linux
	uv audit --preview-features audit-command --locked --python-platform windows

supply-chain: vuln

validate: verify supply-chain
