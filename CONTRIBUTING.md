# Contributing

1. Fork the repository and create a feature branch.
2. Install dependencies: `pip install -e ".[dev]"`
3. Run checks:
   - `ruff check .`
   - `mypy src/`
   - `python -m pytest tests/ -v --tb=short`
4. Open a pull request with a clear description.
