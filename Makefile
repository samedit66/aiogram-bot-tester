.PHONY: tests
tests:
	uv run pytest -vv

.PHONY: check
check:
	uv run ruff check

.PHONY: format
format:
	uv run ruff format
