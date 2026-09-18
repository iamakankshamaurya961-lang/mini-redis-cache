# Contributing to Mini-Redis Cache

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/iamakankshamaurya961-lang/mini-redis-cache.git
   cd mini-redis-cache
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dev dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

## Running the Server

```bash
python3 main.py
```

The dashboard will be available at `http://localhost:8000`.

## Running Tests

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Run only cache engine tests
python -m pytest tests/test_lru_cache.py -v

# Run only API tests
python -m pytest tests/test_api.py -v
```

## Code Quality

```bash
# Lint check
ruff check .

# Auto-fix lint issues
ruff check . --fix

# Type checking
mypy lru_cache.py main.py
```

## Coding Standards

- Use **type hints** on all function signatures
- Write **docstrings** for all public methods
- Keep functions focused and under 30 lines where possible
- Add tests for any new features
- Run `ruff check .` before committing

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass and lint is clean
5. Commit with clear messages (`git commit -m 'Add: amazing feature'`)
6. Push and open a Pull Request
