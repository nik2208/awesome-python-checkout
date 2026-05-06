# Contributing to awesome-python-checkout

Thank you for your interest in contributing! This guide explains how to get started.

## Development setup

```bash
git clone https://github.com/nik2208/awesome-python-checkout
cd awesome-python-checkout
pip install -e ".[dev]"
python -m pytest tests/ -v   # run the full test suite
```

## Project structure

```
awesome_python_checkout/          Library source (Python)
awesome_python_checkout/providers/  Built-in payment providers
tests/                            pytest test suite
```

## How to contribute

1. **Fork** the repository and create a branch from `main`.
2. Make your changes following the style guide below.
3. Add or update tests to cover your change.
4. Run `python -m pytest tests/ -v` — all tests must pass.
5. Open a **Pull Request** against `main`.

## Style guide

- Python 3.11+ with type annotations — no untyped public APIs.
- No new runtime dependencies without discussion in an issue first.
- Public APIs must be documented with docstrings.
- Existing tests must not be removed or weakened.
- Each commit should be a single logical change.

## Adding a new provider

1. Create `awesome_python_checkout/providers/<name>.py`.
2. Define a config `@dataclass` (e.g. `StripeConfig`).
3. Implement all six abstract methods of `BasePaymentProvider`.
4. Export the provider and config from `awesome_python_checkout/providers/__init__.py` and `awesome_python_checkout/__init__.py`.
5. Add tests in `tests/test_providers.py`.
6. Document the provider in `README.md`.

## Reporting bugs & requesting features

Use the [issue templates](.github/ISSUE_TEMPLATE/) provided. Search for existing issues before opening a new one.

## Security issues

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

## Code of Conduct

All contributors are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your work will be licensed under the [MIT License](LICENSE) that covers this project.
