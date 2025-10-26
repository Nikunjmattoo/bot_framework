# Intent Detection Test Suite

Comprehensive test suite for conversation orchestrator intent detection module.

## Test Structure
```
test/conversation_orchestrator/
├── __init__.py                    # Package init
├── conftest.py                    # Shared fixtures
├── test_models.py                 # Model validation tests (62 tests)
├── test_parser.py                 # Parser unit tests (45 tests)
├── test_detector.py               # Detector unit tests (28 tests)
├── test_orchestrator.py           # Orchestrator tests (35 tests)
├── test_integration.py            # Integration tests (12 tests)
├── run_tests.py                   # Test runner
└── README.md                      # This file
```

**Total: 182 tests**

## Test Categories

### 1. Model Tests (`test_models.py`)
- IntentType enum validation
- SingleIntent Pydantic model validation
- IntentOutput Pydantic model validation
- Helper function tests
- Confidence constant tests

### 2. Parser Tests (`test_parser.py`)
- JSON parsing
- Confidence filtering
- Fallback intent creation
- Clarification intent creation
- Response text validation
- Error handling
- Edge cases

### 3. Detector Tests (`test_detector.py`)
- Intent detection flow
- Template fetching and filling
- Enrichment data fetching
- Cold path triggering
- LLM integration (mocked)
- Error handling

### 4. Orchestrator Tests (`test_orchestrator.py`)
- Self-respond path
- Brain-required path
- Response structure
- Adapter validation
- Error handling
- Edge cases

### 5. Integration Tests (`test_integration.py`)
- End-to-end flows with real DB
- Template integration
- Session context integration
- Cold path integration
- Performance tests
- Error recovery

## Running Tests

### Run All Tests
```bash
python test/conversation_orchestrator/run_tests.py
```

### Run Specific Test Category
```bash
python test/conversation_orchestrator/run_tests.py models
python test/conversation_orchestrator/run_tests.py parser
python test/conversation_orchestrator/run_tests.py detector
python test/conversation_orchestrator/run_tests.py orchestrator
python test/conversation_orchestrator/run_tests.py integration
```

### Run with Coverage
```bash
python test/conversation_orchestrator/run_tests.py --coverage
```

### Run with pytest directly
```bash
# All tests
pytest test/conversation_orchestrator/ -v

# Specific file
pytest test/conversation_orchestrator/test_models.py -v

# Specific test
pytest test/conversation_orchestrator/test_models.py::TestIntentTypeEnum::test_all_10_intent_types_defined -v

# With coverage
pytest test/conversation_orchestrator/ --cov=conversation_orchestrator --cov-report=html
```

## Test Coverage Goals

- **Models**: 100% coverage
- **Parser**: 95%+ coverage
- **Detector**: 90%+ coverage
- **Orchestrator**: 90%+ coverage
- **Overall**: 92%+ coverage

## Fixtures

### Database Fixtures
- `test_brand` - Test brand
- `test_llm_model` - Test LLM model
- `test_template_full` - Full intent template with all sections
- `test_session` - Test session
- `test_messages` - Test message history

### Adapter Payload Fixtures
- `base_adapter_payload` - Base adapter payload for testing

### LLM Response Fixtures
- `llm_response_greeting` - Greeting intent response
- `llm_response_goodbye` - Goodbye intent response
- `llm_response_gratitude` - Gratitude intent response
- `llm_response_chitchat` - Chitchat intent response
- `llm_response_action` - Action intent response
- `llm_response_help` - Help intent response
- `llm_response_multi_intent_mixed` - Mixed intents
- `llm_response_multi_intent_self_respond` - Multiple self-respond
- `llm_response_multi_action` - Multiple actions
- `llm_response_low_confidence` - Low confidence
- `llm_response_single_low_confidence` - Single medium confidence
- `llm_response_invalid_json` - Invalid JSON
- `llm_response_missing_intents` - Missing intents field
- `llm_response_empty_intents` - Empty intents list
- `llm_response_missing_confidence` - Missing confidence
- `llm_response_self_respond_without_text` - Invalid: self-respond without text

### Mock Fixtures
- `mock_llm_call_success` - Mock successful LLM call
- `mock_cold_paths` - Mock cold path triggers
- `mock_db_service` - Mock DB service calls

## Test Patterns

### Success Cases
```python
def test_greeting_intent_success(base_adapter_payload, llm_response_greeting):
    """✓ Greeting intent detected successfully"""
    result = detect_intents(base_adapter_payload, "trace-id")
    assert result["self_response"] is True
    assert result["intents"][0]["intent_type"] == "greeting"
```

### Error Cases
```python
def test_invalid_json_raises_error(llm_response_invalid_json):
    """✓ Invalid JSON raises IntentDetectionError"""
    with pytest.raises(IntentDetectionError) as exc:
        parse_intent_response(llm_response_invalid_json["content"])
    assert exc.value.error_code == "INVALID_JSON"
```

### Edge Cases
```python
def test_confidence_exactly_0_7_passes():
    """✓ Confidence = 0.7 passes filter (edge case)"""
    intents = [SingleIntent(intent_type=IntentType.ACTION, confidence=0.7, ...)]
    filtered = _filter_by_confidence(intents)
    assert len(filtered) == 1
```

## Debugging Failed Tests

### View full traceback
```bash
pytest test/conversation_orchestrator/ -v --tb=long
```

### Run only failed tests
```bash
pytest test/conversation_orchestrator/ --lf
```

### Stop on first failure
```bash
pytest test/conversation_orchestrator/ -x
```

### Print output
```bash
pytest test/conversation_orchestrator/ -v -s
```

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:
```yaml
# Example GitHub Actions
- name: Run Orchestrator Tests
  run: |
    pytest test/conversation_orchestrator/ \
      --cov=conversation_orchestrator \
      --cov-report=xml \
      --junitxml=junit.xml
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure all tests pass
3. Maintain >90% coverage
4. Add fixtures to conftest.py
5. Update this README

## Questions?

Contact: [Your Team/Email]