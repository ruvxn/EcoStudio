# EcoStudio ML Tests

Comprehensive test suite for the Instagram Engagement Prediction ML system.

## Quick Start

```bash
# From backend directory
./run_ml_tests.sh

# With coverage
./run_ml_tests.sh --coverage

# Quick tests only
./run_ml_tests.sh --quick
```

## Test Coverage

- ✅ **Feature Engineering**: Temporal & content features
- ✅ **Data Pipeline**: Loading, validation, preprocessing
- ✅ **Integration**: End-to-end ML workflows
- ✅ **50+ Tests**: Unit and integration tests

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (sample data, DB)
├── ml/
│   ├── features/            # Feature engineering tests
│   ├── training/            # Data loading & preprocessing tests
│   └── integration/         # End-to-end pipeline tests
```

## Running Tests

| Command | Description |
|---------|-------------|
| `./run_ml_tests.sh` | Run all tests |
| `./run_ml_tests.sh --unit` | Unit tests only |
| `./run_ml_tests.sh --integration` | Integration tests only |
| `./run_ml_tests.sh --coverage` | Generate coverage report |
| `pytest tests/ml -v` | Run with pytest directly |

## Key Features

### Fixtures
- **Database**: In-memory SQLite for fast tests
- **Sample Data**: 30, 75, or 150 posts with realistic patterns
- **Isolated**: Each test gets fresh database

### Test Categories
- **Unit Tests**: Fast (<0.1s), isolated component tests
- **Integration Tests**: E2E pipeline tests (<5s)

### Coverage Targets
- Overall: >80%
- Critical paths: >90%
- Current: Run `./run_ml_tests.sh --coverage` to check

## Documentation

See [docs/testing-guide.md](../../docs/testing-guide.md) for:
- Detailed test descriptions
- How to write new tests
- Troubleshooting guide
- CI/CD setup

## Requirements

Already included in `requirements.txt`:
- pytest==8.3.4
- pytest-asyncio==0.24.0
- pytest-cov==6.0.0

## Example Output

```
================================ test session starts ================================
tests/ml/features/test_temporal.py::TestExtractTemporalFeatures::test_basic_temporal_features PASSED
tests/ml/features/test_temporal.py::TestExtractTemporalFeatures::test_cyclical_encoding PASSED
tests/ml/integration/test_ml_pipeline.py::TestMLPipelineIntegration::test_complete_training_pipeline PASSED

======================== 50 passed in 8.23s =========================
```

## Troubleshooting

**Import errors?**
```bash
export PYTHONPATH="${PYTHONPATH}:${PWD}"
```

**Slow tests?**
```bash
./run_ml_tests.sh --quick  # Skip slow tests
```

**See test output?**
```bash
pytest tests/ml -s  # Show print statements
```

## Next Steps

1. ✅ Tests are ready to run
2. Run: `./run_ml_tests.sh --coverage`
3. Open: `htmlcov/index.html` to see coverage report
4. Add your own tests following the patterns in existing test files

Happy testing! 🧪
