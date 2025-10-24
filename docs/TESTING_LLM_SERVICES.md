# Testing Non-Deterministic LLM Services

## The Challenge

Testing LLM services is challenging because:
1. **Non-deterministic outputs** - Same input can produce different outputs
2. **External API dependency** - Requires network calls
3. **Cost** - Real API calls cost money
4. **Slow** - Network latency makes tests slow

## The Solution: Test YOUR Logic, Not the LLM

**Critical Principle:** Mock the LLM client to isolate and test YOUR business logic, not to verify that mocks work.

---

## What Makes a Valuable Test?

### ✅ **GOOD: Tests YOUR Business Logic**

```python
# GOOD: Tests that WE validate empty input
@pytest.mark.asyncio
async def test_empty_transcription_rejected(llm_service):
    with pytest.raises(ValidationError) as exc_info:
        await llm_service.parse_workout("")

    assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
```
**Why good?** Tests OUR validation rule that empty = invalid.

---

```python
# GOOD: Tests that WE detect rate limits correctly
@pytest.mark.asyncio
async def test_detect_rate_limit_by_status_code_429(llm_service):
    error = Exception("Rate limit")
    error.status_code = 429
    llm_service.client.create.side_effect = error

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await llm_service.parse_workout("test")

    assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED
```
**Why good?** Tests OUR error classification logic (status_code == 429 → rate limit).

---

```python
# GOOD: Tests that WE strip markdown
@pytest.mark.asyncio
async def test_markdown_wrapper_stripped(llm_service):
    mock_response.content = "```json\n{\"data\": \"value\"}\n```"

    result = await llm_service.parse_workout("test")

    assert result == {"data": "value"}  # Markdown was stripped
```
**Why good?** Tests OUR transformation logic (removing ```json markers).

---

### ❌ **BAD: Circular Mock Testing**

```python
# BAD: Mock returns X, we assert we get X back
@pytest.mark.asyncio
async def test_parse_valid_response(llm_service):
    workout_data = {"exercises": [{"name": "supino", "sets": 3}]}
    mock_response.content = json.dumps(workout_data)

    result = await llm_service.parse_workout("test")

    assert result["exercises"][0]["name"] == "supino"  # Just testing the mock!
    assert result["exercises"][0]["sets"] == 3  # Circular!
```
**Why bad?** We're just verifying the mock returns what we configured. Zero value.

---

```python
# BAD: Verifying we called the API
@pytest.mark.asyncio
async def test_api_called_once(llm_service):
    await llm_service.parse_workout("test")

    llm_service.client.create.assert_called_once()  # So what?
```
**Why bad?** Can see this in the code. Doesn't test any logic.

---

```python
# BAD: Mock has 50 exercises, assert we get 50
@pytest.mark.asyncio
async def test_large_response(llm_service):
    mock_response.content = json.dumps({"exercises": [ex for ex in range(50)]})

    result = await llm_service.parse_workout("test")

    assert len(result["exercises"]) == 50  # Circular!
```
**Why bad?** Just counting what we put in the mock. No business logic tested.

---

## Our Testing Strategy

### What We Test (28 tests)

**1. Input Validation (4 tests)** - OUR validation rules
- Empty transcription → rejected
- Whitespace-only → rejected
- Length > MAX_TRANSCRIPTION_LENGTH → rejected
- Length == MAX_TRANSCRIPTION_LENGTH → accepted (boundary test)

**2. Error Detection & Classification (13 tests)** - OUR error parsing
- Empty/None response → LLM_INVALID_RESPONSE
- HTTP 429 → LLM_RATE_LIMIT_EXCEEDED
- HTTP 401 → GROQ_API_ERROR
- HTTP 504 → LLM_TIMEOUT
- "rate_limit" in message → LLM_RATE_LIMIT_EXCEEDED
- "timeout" in message → LLM_TIMEOUT
- "invalid key" in message → GROQ_API_ERROR
- Generic error → LLM_PARSING_FAILED

**3. Data Transformation (2 tests)** - OUR parsing logic
- Strip ```json markdown wrappers
- Strip whitespace from responses

**4. JSON Validation (4 tests)** - OUR type checking
- Malformed JSON → LLM_INVALID_RESPONSE
- JSON array when object expected → error
- JSON string when object expected → error
- Plain text (not JSON) → error

**5. Prompt Building (3 tests)** - OUR prompt logic
- Transcription included in prompt
- Key instructions present
- Special characters handled

**6. Exception Handling (2 tests)** - OUR re-raise logic
- ValidationError re-raised without wrapping
- Concurrent async calls handled

---

## Test Reduction: 39 → 28 Tests

### Removed Tests (No Business Value)

❌ **Removed:** `test_init_with_api_key_success`
**Why:** Just verifies mock setup worked.

❌ **Removed:** `test_parse_valid_json_response`
**Why:** Mock returns workout data, we verify we get it back. Circular.

❌ **Removed:** `test_parse_minimal_valid_response`
**Why:** Same as above, just with minimal data. Circular.

❌ **Removed:** `test_api_call_parameters`
**Why:** Just verifies we passed parameters through. No logic.

❌ **Removed:** `test_api_called_once_per_parse`
**Why:** Just counting API calls. No business logic.

❌ **Removed:** `test_very_large_valid_json_response`
**Why:** Mock returns 50 exercises, we count 50. Circular.

❌ **Removed:** `test_unicode_characters_in_response`
**Why:** Mock has unicode, we verify unicode present. Circular.

❌ **Removed:** `test_response_truncation_in_error_log`
**Why:** Tests exception class behavior, not our code.

❌ **Removed:** `test_network_error`
**Why:** Falls through to generic handler. No unique logic.

❌ **Removed:** `test_build_prompt_with_line_breaks`
**Why:** No different logic than special characters test.

❌ **Removed:** `test_llm_parsing_error_from_invalid_json_is_raised`
**Why:** Already covered by `test_reject_malformed_json`.

---

## Code Examples

### Example 1: Testing Validation Boundaries

```python
@pytest.mark.asyncio
async def test_transcription_length_limit_enforced(llm_service, monkeypatch):
    """Test that we enforce MAX_TRANSCRIPTION_LENGTH limit"""
    monkeypatch.setattr(settings, "MAX_TRANSCRIPTION_LENGTH", 100)

    long_transcription = "a" * 101  # Exceeds by 1

    with pytest.raises(ValidationError) as exc_info:
        await llm_service.parse_workout(long_transcription)

    error = exc_info.value
    assert error.error_code == ErrorCode.VALUE_OUT_OF_RANGE
    assert "100" in error.message  # Limit mentioned in error
```

**Tests OUR logic:**
- Boundary check (101 > 100)
- Correct error code returned
- Error message includes the limit

---

### Example 2: Testing Error Detection

```python
@pytest.mark.asyncio
async def test_detect_rate_limit_by_message_content(llm_service):
    """Test that we detect rate limits by message content"""
    error = Exception("rate_limit exceeded by user")
    llm_service.client.chat.completions.create.side_effect = error

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await llm_service.parse_workout("Test")

    assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED
```

**Tests OUR logic:**
- String parsing ("rate_limit" in error message)
- Error classification
- Exception transformation

---

### Example 3: Testing Data Transformation

```python
@pytest.mark.asyncio
async def test_markdown_wrapper_stripped(llm_service, valid_workout_json):
    """Test that we strip markdown code blocks from LLM response"""
    mock_response = Mock()
    mock_message.content = f"```json\n{json.dumps(valid_workout_json)}\n```"
    # ... setup mock ...

    result = await llm_service.parse_workout("Test transcription")

    # Verify markdown was stripped AND JSON was parsed
    assert result == valid_workout_json
```

**Tests OUR logic:**
- Regex/string replacement (removing ```json markers)
- JSON parsing after transformation
- Output equals expected structure

---

## Key Testing Fixtures

### Mock LLM Client
```python
@pytest.fixture
def mock_groq_client():
    """Mock Groq client - no real API calls"""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock()
    return mock
```

### LLM Service with Mocked Client
```python
@pytest.fixture
def llm_service(mock_groq_client, monkeypatch):
    """Service instance with fake API key and mocked client"""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    with patch("services.async_llm_service.AsyncGroq") as mock:
        mock.return_value = mock_groq_client
        service = LLMParsingService()
        service.client = mock_groq_client
        return service
```

---

## Test Results

```
28 tests, 28 passed (100%) in 0.32s

Test Categories:
├─ Initialization: 2 tests
├─ Input Validation: 4 tests
├─ Data Transformation: 2 tests
├─ Error Detection: 13 tests
├─ JSON Validation: 4 tests
├─ Prompt Building: 3 tests
└─ Exception Handling: 2 tests
```

**28% faster than before** (0.32s vs 0.42s) by removing circular tests.

---

## When to Use Integration Tests

While unit tests use mocks, keep a **few** integration tests with real API:

```python
@pytest.mark.integration
@pytest.mark.slow
async def test_real_groq_api():
    """Integration test with real Groq API"""
    if not os.getenv("GROQ_API_KEY"):
        pytest.skip("Requires real API key")

    service = LLMParsingService()
    result = await service.parse_workout("Fiz supino 3x12 com 60kg")

    # Basic sanity check only
    assert isinstance(result, dict)
    assert "resistance_exercises" in result
```

**Use real API for:**
- Verifying API contract hasn't changed (run weekly)
- Debugging production issues (run manually)

**Keep them:**
- Few in number (1-2 tests max)
- Marked as `@pytest.mark.integration` and `@pytest.mark.slow`
- Skipped in CI/CD by default

---

## Summary: Value-Driven Testing

### Test These (Add Value):
✅ YOUR validation rules
✅ YOUR error detection logic
✅ YOUR data transformations
✅ YOUR business rules
✅ YOUR exception handling
✅ YOUR boundary conditions

### Don't Test These (No Value):
❌ Mock returns what you set it to return
❌ External APIs work (that's their job)
❌ Simple data pass-through
❌ That you called an API (visible in code)
❌ Counting things you put in the mock

---

## Applying This to Other Services

Use the same principle for:

**Audio Service (Whisper)**
- ✅ Test: Audio file validation (size, format)
- ✅ Test: Error handling (transcription failed)
- ❌ Don't: Mock transcription result and assert you get it

**Workout Service**
- ✅ Test: Session timeout calculation (3 hours)
- ✅ Test: Weight/reps array validation
- ✅ Test: State transitions (ATIVA → FINALIZADA)
- ❌ Don't: Mock workout data and count exercises

**Analytics Service**
- ✅ Test: Volume calculations (sets × reps × weight)
- ✅ Test: Date range filtering
- ✅ Test: Aggregation formulas
- ❌ Don't: Mock 5 workouts, assert average is 5

---

## The Golden Rule

**If removing the mock breaks the test, it's testing business logic (GOOD).**
**If removing the mock doesn't break the test, it's testing the mock (BAD).**

Example:
```python
# Remove this line:
mock_response.content = json.dumps({"exercises": [...]})

# Does this assertion still make sense?
assert len(result["exercises"]) == 3  # ❌ NO - test was circular

# Does this assertion still make sense?
assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD  # ✅ YES - tests our rule
```
