# Repository Guidelines

## Project Structure & Module Organization

This is a Python monorepo managed with `uv` workspaces. The core package lives in `agents-core/vision_agents/`, with CLI code under `agents-core/vision_agents/cli/` and framework code under `agents-core/vision_agents/core/`. Provider integrations live in `plugins/<provider>/`, each with its own `pyproject.toml`, `README.md`, package code under `vision_agents/plugins/<provider>/`, and usually `tests/` plus `example/`. Shared tests are in `tests/`; test assets are in `tests/test_assets/`. Runnable samples are in `examples/`, and contributor docs are in `README.md`, `DEVELOPMENT.md`, `SECURITY.md`, and `CHANGELOG.md`.

## Build, Test, and Development Commands

Install locally with:

```bash
uv venv --python 3.12.11
uv sync --all-extras --dev
pre-commit install
```

Use `uv` for all project commands. `uv run python dev.py check` runs formatting checks, dependency validation, mypy, and non-integration tests. `uv run pytest -m "not integration"` runs unit tests. `uv run pytest -m "integration"` runs integration tests and requires local secrets. `uv run ruff check --fix` applies lint fixes; `uv run ruff format .` formats Python files. Run examples with `uv run examples/01_simple_agent_example/simple_agent_example.py run`.

## Coding Style & Naming Conventions

Write typed Python compatible with Python `>=3.10`; Python 3.12 is recommended. Use 4-space indentation, `snake_case` functions and variables, `PascalCase` classes, and leading underscores for private members. Keep imports grouped as stdlib, third-party, local package, then relative imports. Prefer public re-exports over importing private modules. Keep docstrings short and Google style when needed.

## Testing Guidelines

Tests use pytest with `asyncio_mode = auto`; `@pytest.mark.asyncio` is not required. Files, functions, and classes follow `test_*.py`, `test_*`, and `Test*`. Mark external-service tests with `@pytest.mark.integration`; keep default test runs free of secrets and network requirements. Add behavior-focused tests near the relevant package or plugin.

## Commit & Pull Request Guidelines

History mostly uses concise conventional prefixes such as `feat:`, `fix(scope):`, `test(scope):`, `docs:`, and `chore(deps):`. Keep commits imperative and scoped when useful, for example `fix(gemini): handle tool fixtures`. Pull requests should describe the change, list tests run, link related issues, and include screenshots or logs for user-visible examples.

## Security & Configuration Tips

Copy example environment files to local `.env` files as needed, but never commit secrets. Integration tests and provider examples may require API keys. For plugin packaging, keep `[tool.hatch.build.targets.wheel] packages = ["vision_agents"]` so wheels do not include tests or examples.
