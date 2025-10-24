# Testing Non-Deterministic LLM Services

## The Challenge

Testing LLM (Large Language Model) services is challenging because:
1. **Non-deterministic outputs** - Same input can produce different outputs
2. **External API dependency** - Requires network calls to third-party services
3. **Cost** - Real API calls cost money
4. **Slow** - Network latency makes tests slow
5. **Unpredictable** - API might be down or rate-limited during testing

## The Solution: Mock the LLM Client

**Key Principle:** We don't test if the LLM works (that's the provider's job). We test if **OUR code** correctly handles various LLM responses.

### Testing Strategy

```
┌─────────────────┐
│  Our Test Code  │
└────────┬────────┘
         │
         ├──> Mock LLM Client (controlled responses)
         │
         └──> Our Parsing Logic (what we're testing)
                │
                ├──> Valid JSON parsing
                ├──> Error handling
                ├──> Edge cases
                └──> Exception handling
```

## What We Test

### 1. **Initialization Tests**
- ✅ Missing API key error
- ✅ Successful initialization
- ✅ Client creation failure

### 2. **Input Validation Tests**
- ✅ Empty transcription
- ✅ Whitespace-only input
- ✅ Input exceeding length limits
- ✅ Input at exactly max length

### 3. **LLM Response Parsing Tests** (Mocked Responses)
- ✅ Valid JSON response
- ✅ JSON wrapped in markdown (```json ... ```)
- ✅ Minimal valid response
- ✅ Empty choices array
- ✅ None/null responses
- ✅ Empty message content

### 4. **Invalid JSON Handling**
- ✅ Malformed JSON syntax
- ✅ JSON array instead of object
- ✅ JSON string instead of object
- ✅ Plain text (not JSON)

### 5. **Error Handling Tests**
- ✅ Rate limit errors (HTTP 429)
- ✅ Authentication errors (HTTP 401)
- ✅ Timeout errors (HTTP 504)
- ✅ Network errors
- ✅ Generic unexpected errors

### 6. **Edge Cases**
- ✅ Very large JSON responses
- ✅ Unicode characters
- ✅ Extra whitespace
- ✅ Concurrent API calls
- ✅ Response truncation in logs

## Code Examples

### Example 1: Mocking Valid LLM Response

```python
@pytest.mark.asyncio
async def test_parse_valid_json_response(llm_service, mock_groq_response):
    """Test parsing of valid JSON response from LLM"""
    # Set up mock to return our controlled response
    llm_service.client.chat.completions.create.return_value = mock_groq_response

    # Call the actual service method
    result = await llm_service.parse_workout("Fiz 3 séries de supino com 60kg")

    # Verify our parsing logic works correctly
    assert isinstance(result, dict)
    assert "resistance_exercises" in result
    assert len(result["resistance_exercises"]) == 2
```

**What we're testing:** Our code correctly extracts data from a valid LLM response.

**What we're NOT testing:** Whether Groq API actually works.

---

### Example 2: Mocking Rate Limit Error

```python
@pytest.mark.asyncio
async def test_rate_limit_error_with_429_status(llm_service):
    """Test handling of rate limit error with HTTP 429 status"""
    # Create a mock error with HTTP 429 status
    error = Exception("Rate limit exceeded")
    error.status_code = 429

    # Make the mock raise this error
    llm_service.client.chat.completions.create.side_effect = error

    # Verify our code handles it correctly
    with pytest.raises(ServiceUnavailableError) as exc_info:
        await llm_service.parse_workout("Test transcription")

    error = exc_info.value
    assert error.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED
    assert "Limite de taxa" in error.message
```

**What we're testing:** Our error detection logic correctly identifies rate limits.

---

### Example 3: Mocking Malformed JSON

```python
@pytest.mark.asyncio
async def test_invalid_json_syntax(llm_service):
    """Test handling of malformed JSON"""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()

    # Simulate LLM returning invalid JSON
    mock_message.content = '{"invalid": json syntax}'
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    llm_service.client.chat.completions.create.return_value = mock_response

    # Verify our code handles invalid JSON gracefully
    with pytest.raises(LLMParsingError) as exc_info:
        await llm_service.parse_workout("Test transcription")

    error = exc_info.value
    assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
    assert "não é JSON válido" in error.message
```

**What we're testing:** Our JSON parsing error handling works correctly.

---

## Key Testing Fixtures

### 1. Mock Groq Client

```python
@pytest.fixture
def mock_groq_client():
    """Mock Groq client for testing"""
    mock = AsyncMock()
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock()
    return mock
```

This creates a fake Groq client that we control completely.

---

### 2. LLM Service Fixture

```python
@pytest.fixture
def llm_service(mock_groq_client, monkeypatch):
    """Create LLMParsingService with mocked Groq client"""
    # Set fake API key to avoid initialization error
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key-123")

    with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
        mock_async_groq.return_value = mock_groq_client
        service = LLMParsingService()
        service.client = mock_groq_client
        return service
```

This creates our service with a mocked client instead of a real one.

---

### 3. Valid Workout JSON Fixture

```python
@pytest.fixture
def valid_workout_json() -> Dict[str, Any]:
    """Valid workout JSON response from LLM"""
    return {
        "body_weight_kg": 75.5,
        "energy_level": 8,
        "resistance_exercises": [
            {
                "name": "supino reto com barra",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [60, 70, 80],
                # ... more fields
            }
        ],
        # ... more data
    }
```

This provides a realistic LLM response for our tests.

---

## Benefits of This Approach

### ✅ **Deterministic**
- Same test always produces same result
- No random failures

### ✅ **Fast**
- No network calls
- Tests run in milliseconds

### ✅ **Free**
- No API costs

### ✅ **Reliable**
- Tests work offline
- Never affected by API downtime

### ✅ **Comprehensive**
- Can test rare error scenarios
- Can test edge cases that are hard to reproduce with real API

### ✅ **Focused**
- Tests OUR code, not the LLM provider's code
- Clear pass/fail criteria

---

## Testing Coverage for async_llm_service.py

```
✅ 39 tests / 39 passed (100%)

Test Categories:
├─ Initialization: 3 tests
├─ Input Validation: 4 tests
├─ Response Parsing: 7 tests
├─ Invalid JSON: 4 tests
├─ Error Handling: 7 tests
├─ Prompt Building: 3 tests
├─ API Parameters: 2 tests
├─ Edge Cases: 7 tests
└─ Exception Re-raising: 2 tests
```

---

## When to Use Real API (Integration Tests)

While unit tests use mocks, you should also have a **small number** of integration tests with real API:

```python
@pytest.mark.integration
@pytest.mark.slow
async def test_real_groq_api():
    """Integration test with real Groq API"""
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("Real API key required")

    service = LLMParsingService()
    result = await service.parse_workout("Fiz 3 séries de supino com 60kg")

    # Basic sanity check
    assert isinstance(result, dict)
    assert "resistance_exercises" in result
```

**Use real API tests for:**
- Verifying API contract hasn't changed
- Testing actual LLM behavior (run manually, not in CI/CD)
- Debugging production issues

**But keep them:**
- Few in number (expensive and slow)
- Marked as `@pytest.mark.integration` and `@pytest.mark.slow`
- Skipped in normal test runs

---

## Summary: How to Test LLM Code

1. **Mock the LLM client** - Control responses completely
2. **Test parsing logic** - Verify you handle valid responses correctly
3. **Test error handling** - Simulate all possible errors
4. **Test edge cases** - Malformed data, empty responses, etc.
5. **Use fixtures** - Reusable test data and mocks
6. **Make tests fast** - No real API calls in unit tests
7. **Add few integration tests** - Verify real API works (run sparingly)

---

## Next Steps

Apply this same pattern to test other services:
- **Audio transcription** - Mock Whisper API
- **Database operations** - Use test database or SQLite in-memory
- **Telegram handlers** - Mock Telegram Update/Context objects
- **File operations** - Use temporary directories

**The principle is always the same:** Mock external dependencies, test YOUR code.
