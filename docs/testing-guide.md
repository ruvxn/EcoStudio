## ML Testing Guide

Complete testing documentation for the EcoStudio ML Engagement Prediction system.

## Quick Start

```bash
# Navigate to backend directory
cd backend

# Run all ML tests
./run_ml_tests.sh

# Run with coverage report
./run_ml_tests.sh --coverage

# Run only unit tests
./run_ml_tests.sh --unit

# Run integration tests
./run_ml_tests.sh --integration
```

## Test Structure

```
backend/tests/
├── conftest.py                    # Shared fixtures and configuration
├── ml/
│   ├── features/                  # Feature engineering tests
│   │   ├── test_temporal.py       # Temporal feature tests
│   │   ├── test_content.py        # Content feature tests
│   │   └── test_engineering.py    # Feature orchestration tests
│   ├── training/                  # Training pipeline tests
│   │   ├── test_data_loader.py    # Data loading tests
│   │   └── test_preprocessor.py   # Data preprocessing tests
│   └── integration/               # End-to-end tests
│       └── test_ml_pipeline.py    # Complete pipeline tests
```

## Test Categories

### Unit Tests
Fast, isolated tests for individual components.

**Feature Engineering Tests** (`tests/ml/features/`)
- Temporal feature extraction (hour, day, cyclical encoding)
- Content feature extraction (hashtags, emojis, CTAs)
- Feature engineering orchestration
- One-hot encoding and scaling

**Data Processing Tests** (`tests/ml/training/`)
- Database query and data loading
- Data validation and cleaning
- Train/test splitting
- Historical averages calculation

### Integration Tests
Tests that verify multiple components working together.

**Pipeline Tests** (`tests/ml/integration/`)
- Complete training pipeline (data → model)
- Complete prediction pipeline (model → predictions)
- Confidence scoring integration
- MLService end-to-end workflow
- Model persistence and loading

## Fixtures

### Database Fixtures
- `test_db`: In-memory SQLite database for testing
- `sample_account`: Sample social media account
- `sample_posts_small`: 30 posts (minimum for training)
- `sample_posts_medium`: 75 posts (medium dataset)
- `sample_posts_large`: 150 posts (large dataset with advanced features)

### Data Fixtures
- `sample_dataframe`: Pandas DataFrame with 50 sample posts
- `trained_model_path`: Temporary directory for model storage

## Running Tests

### All Tests
```bash
./run_ml_tests.sh
```

### Specific Test Categories
```bash
# Unit tests only
./run_ml_tests.sh --unit

# Integration tests only
./run_ml_tests.sh --integration

# Feature engineering tests only
./run_ml_tests.sh --features

# Quick tests (exclude slow tests)
./run_ml_tests.sh --quick
```

### With Options
```bash
# Verbose output
./run_ml_tests.sh -v

# Generate coverage report
./run_ml_tests.sh --coverage

# Combine options
./run_ml_tests.sh --unit --coverage -v
```

### Using Pytest Directly
```bash
# Run all ML tests
pytest tests/ml

# Run specific test file
pytest tests/ml/features/test_temporal.py

# Run specific test class
pytest tests/ml/features/test_temporal.py::TestExtractTemporalFeatures

# Run specific test function
pytest tests/ml/features/test_temporal.py::TestExtractTemporalFeatures::test_basic_temporal_features

# Run tests matching a pattern
pytest -k "temporal"

# Run with markers
pytest -m "unit"
pytest -m "integration"
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Tests that take >1 second
- `@pytest.mark.ml` - ML-related tests
- `@pytest.mark.features` - Feature engineering tests
- `@pytest.mark.training` - Model training tests
- `@pytest.mark.prediction` - Prediction generation tests

## Coverage Reporting

### Generate Coverage Report
```bash
./run_ml_tests.sh --coverage
```

This generates:
- **Terminal report**: Shows coverage percentages
- **HTML report**: Detailed coverage at `backend/htmlcov/index.html`

### View HTML Coverage Report
```bash
# Open in browser (Mac)
open backend/htmlcov/index.html

# Open in browser (Linux)
xdg-open backend/htmlcov/index.html
```

### Coverage Targets
- **Overall**: >80% coverage
- **Critical paths**: >90% coverage (training, prediction)
- **Utility functions**: >70% coverage

## Writing New Tests

### Test Template
```python
"""
Tests for [component name]
"""
import pytest

from app.ml.[module] import [function_or_class]


class Test[ComponentName]:
    """Test [component] functionality"""

    def test_[specific_behavior](self, fixture_name):
        """Test that [expected behavior]"""
        # Arrange
        input_data = ...

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_value
```

### Best Practices

1. **Descriptive Names**: Test names should describe what they test
   ```python
   # Good
   def test_temporal_features_include_cyclical_encoding(self):

   # Bad
   def test_features(self):
   ```

2. **One Assert Per Test**: Focus each test on one behavior
   ```python
   # Good
   def test_hour_extraction(self):
       assert result["hour"] == 10

   def test_day_extraction(self):
       assert result["day_of_week"] == 2

   # Avoid
   def test_all_features(self):
       assert result["hour"] == 10
       assert result["day_of_week"] == 2
       assert result["is_weekend"] == 0
   ```

3. **Use Fixtures**: Leverage pytest fixtures for setup
   ```python
   def test_with_sample_data(self, sample_dataframe):
       result = process_data(sample_dataframe)
       assert len(result) > 0
   ```

4. **Test Edge Cases**:
   - Empty inputs
   - Null values
   - Extreme values
   - Invalid inputs

5. **Mock External Dependencies**: Use mocks for external services
   ```python
   from unittest.mock import patch, MagicMock

   @patch('app.ml.service.external_api')
   def test_with_mock(self, mock_api):
       mock_api.return_value = expected_response
       result = function_that_calls_api()
       assert result is not None
   ```

## Continuous Integration

### GitHub Actions Example
```yaml
name: ML Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        cd backend
        pip install -r requirements.txt

    - name: Run ML tests
      run: |
        cd backend
        ./run_ml_tests.sh --coverage

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Troubleshooting

### Common Issues

**Issue**: `ImportError: No module named 'app'`
```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/backend"
```

**Issue**: Database connection errors
```bash
# Solution: Tests use in-memory SQLite, no database needed
# If seeing connection errors, check test_db fixture in conftest.py
```

**Issue**: Tests fail with "Insufficient data"
```bash
# Solution: Use appropriate fixture
# sample_posts_small: 30 posts (minimum)
# sample_posts_medium: 75 posts
# sample_posts_large: 150 posts
```

**Issue**: `ModuleNotFoundError` for test dependencies
```bash
# Solution: Ensure test dependencies are installed
pip install pytest pytest-asyncio pytest-cov
```

## Performance Benchmarking

### Measuring Test Performance
```bash
# Show test durations
pytest --durations=10 tests/ml

# Show slowest tests
pytest --durations=0 tests/ml
```

### Performance Targets
- Unit tests: <0.1s each
- Integration tests: <5s each
- Full test suite: <30s total

## Test Data

### Sample Post Generation
The `_create_sample_posts` function in `conftest.py` generates realistic test data:

- **Temporal patterns**: Peak engagement at 18:00 (evening)
- **Weekend boost**: 30% higher engagement on weekends
- **Content type effects**: Videos/Reels get 40% more engagement
- **Hashtag optimization**: 5-10 hashtags perform best
- **Emoji impact**: Posts with emojis get 10% boost

### Customizing Test Data
```python
# In your test
def test_with_custom_data(self, test_db, sample_account):
    # Create custom posts
    posts = _create_sample_posts(
        db=test_db,
        account=sample_account,
        n_posts=100  # Custom size
    )
```

## Debugging Tests

### Run with pdb debugger
```bash
pytest --pdb tests/ml/features/test_temporal.py
```

### Print output during tests
```bash
pytest -s tests/ml  # Show print statements
```

### Run specific failing test
```bash
pytest tests/ml/features/test_temporal.py::test_function_name -vv
```

## Next Steps

1. **Run the test suite**: `./run_ml_tests.sh`
2. **Check coverage**: `./run_ml_tests.sh --coverage`
3. **Add new tests**: Follow the template above
4. **Set up CI/CD**: Use the GitHub Actions example

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Testing Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)

---

**Last Updated**: November 13, 2025
**Test Coverage Target**: 80%+
**Current Test Count**: 50+ tests
