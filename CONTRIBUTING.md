# Contributing to MatchKit

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/yourorg/matchkit.git
cd matchkit
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

## Running Tests

```bash
pytest
pytest --cov=. --cov-report=html   # with coverage
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for any new functionality
3. Ensure `ruff check .` and `pytest` pass
4. Submit a PR with a clear description of the change

## Contribution License

By submitting a contribution, you agree that your contribution is licensed under
the Apache-2.0 license for this project.

## Reporting Issues

Please use GitHub Issues with the provided templates for bug reports and feature requests.
