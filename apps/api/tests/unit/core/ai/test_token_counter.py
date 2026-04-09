"""
Tests for Token Counter & Cost Estimator.

P3.1: Validates tiktoken-based pre-execution cost prediction.
"""


from src.core.ai.token_counter import (
    MODEL_PRICING,
    CostBreakdown,
    TokenCounter,
    TokenEstimate,
    count_tokens,
    estimate_cost,
    get_token_counter,
)

# ===========================================
# TOKEN COUNTER BASIC TESTS
# ===========================================


class TestTokenCounter:
    """Tests for TokenCounter class."""

    def test_count_tokens_empty_string(self):
        """Empty string returns 0 tokens."""
        counter = TokenCounter()
        assert counter.count_tokens("") == 0

    def test_count_tokens_simple_text(self):
        """Simple text has reasonable token count."""
        counter = TokenCounter()
        tokens = counter.count_tokens("Hello, world!")
        # "Hello, world!" should be around 4 tokens
        assert 2 <= tokens <= 6

    def test_count_tokens_spanish_text(self):
        """Spanish text tokenizes correctly."""
        counter = TokenCounter()
        text = "El contratista entregará el proyecto en 6 meses."
        tokens = counter.count_tokens(text)
        # Spanish text should tokenize reasonably
        assert tokens > 5

    def test_count_tokens_long_text(self):
        """Longer text has proportionally more tokens."""
        counter = TokenCounter()
        short = counter.count_tokens("Hello")
        long = counter.count_tokens("Hello " * 100)
        assert long > short * 50  # Should scale roughly linearly

    def test_count_message_tokens_single_message(self):
        """Single message has overhead + content tokens."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": "Hello"}]
        tokens = counter.count_message_tokens(messages)
        # Should be content + overhead (~4 per message + 3 reply priming)
        assert tokens >= 5

    def test_count_message_tokens_conversation(self):
        """Multi-turn conversation counts correctly."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "2+2 equals 4."},
            {"role": "user", "content": "Thanks!"},
        ]
        tokens = counter.count_message_tokens(messages)
        # 3 messages × ~4 overhead + content + 3 reply priming
        assert tokens >= 15

    def test_count_message_tokens_empty_list(self):
        """Empty message list returns minimal tokens (reply priming only)."""
        counter = TokenCounter()
        tokens = counter.count_message_tokens([])
        assert tokens == 3  # Reply priming overhead


# ===========================================
# COST ESTIMATION TESTS
# ===========================================


class TestCostEstimation:
    """Tests for cost estimation functionality."""

    def test_estimate_request_basic(self):
        """Basic request estimation works."""
        counter = TokenCounter()
        estimate = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello, how are you?"}],
        )

        assert isinstance(estimate, TokenEstimate)
        assert estimate.input_tokens > 0
        assert estimate.estimated_output_tokens > 0
        assert estimate.total_cost_usd > 0
        assert estimate.model == "claude-sonnet-4-20250514"

    def test_estimate_request_with_system_prompt(self):
        """System prompt tokens are counted."""
        counter = TokenCounter()

        # Without system prompt
        estimate_no_system = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # With system prompt
        estimate_with_system = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            system="You are a helpful assistant specialized in contract analysis.",
        )

        assert estimate_with_system.system_tokens > 0
        assert estimate_with_system.input_tokens > estimate_no_system.input_tokens

    def test_estimate_request_custom_output_tokens(self):
        """Custom expected output tokens affects cost."""
        counter = TokenCounter()

        estimate_low = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            expected_output_tokens=100,
        )

        estimate_high = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            expected_output_tokens=4000,
        )

        assert estimate_high.total_cost_usd > estimate_low.total_cost_usd

    def test_estimate_request_context_usage(self):
        """Context usage percentage is calculated correctly."""
        counter = TokenCounter()
        estimate = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            expected_output_tokens=100,
        )

        assert estimate.context_usage_percent > 0
        assert estimate.context_usage_percent < 100
        assert estimate.context_limit == 200_000

    def test_estimate_request_high_context_warning(self):
        """High context usage generates warning."""
        counter = TokenCounter()

        # Create a very large message to trigger warning
        large_content = "word " * 50000  # ~50K tokens
        estimate = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": large_content}],
            expected_output_tokens=100000,
        )

        # Should have warnings about high context usage
        assert len(estimate.warnings) > 0


# ===========================================
# MODEL PRICING TESTS
# ===========================================


class TestModelPricing:
    """Tests for model pricing configuration."""

    def test_pricing_opus_most_expensive(self):
        """Opus is most expensive model."""
        assert MODEL_PRICING["opus"]["input"] > MODEL_PRICING["sonnet"]["input"]
        assert MODEL_PRICING["opus"]["output"] > MODEL_PRICING["sonnet"]["output"]

    def test_pricing_haiku_cheapest(self):
        """Haiku is cheapest model."""
        assert MODEL_PRICING["haiku"]["input"] < MODEL_PRICING["sonnet"]["input"]
        assert MODEL_PRICING["haiku"]["output"] < MODEL_PRICING["sonnet"]["output"]

    def test_cost_difference_by_model(self):
        """Different models produce different costs."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": "Analyze this contract."}]

        haiku = counter.estimate_request(
            model="claude-haiku-4-20250514",
            messages=messages,
            expected_output_tokens=500,
        )

        sonnet = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=messages,
            expected_output_tokens=500,
        )

        opus = counter.estimate_request(
            model="claude-opus-4-20250514",
            messages=messages,
            expected_output_tokens=500,
        )

        assert haiku.total_cost_usd < sonnet.total_cost_usd
        assert sonnet.total_cost_usd < opus.total_cost_usd

    def test_unknown_model_uses_default_pricing(self):
        """Unknown model falls back to default pricing."""
        counter = TokenCounter()
        estimate = counter.estimate_request(
            model="unknown-future-model",
            messages=[{"role": "user", "content": "Hello"}],
            expected_output_tokens=100,
        )

        # Should still work with default pricing
        assert estimate.total_cost_usd > 0


# ===========================================
# COST BREAKDOWN TESTS
# ===========================================


class TestCostBreakdown:
    """Tests for detailed cost breakdown."""

    def test_calculate_cost_basic(self):
        """Basic cost calculation works."""
        counter = TokenCounter()
        breakdown = counter.calculate_cost(
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
        )

        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.input_tokens == 1000
        assert breakdown.output_tokens == 500
        assert breakdown.input_cost_usd > 0
        assert breakdown.output_cost_usd > 0
        expected_total = round(breakdown.input_cost_usd + breakdown.output_cost_usd, 6)
        assert breakdown.total_cost_usd == expected_total

    def test_calculate_cost_sonnet_pricing(self):
        """Sonnet pricing is $3/1M input, $15/1M output."""
        counter = TokenCounter()
        breakdown = counter.calculate_cost(
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )

        assert breakdown.input_rate_per_million == 3.0
        assert breakdown.output_rate_per_million == 15.0
        assert abs(breakdown.input_cost_usd - 3.0) < 0.01
        assert abs(breakdown.output_cost_usd - 15.0) < 0.01


# ===========================================
# BATCH ESTIMATION TESTS
# ===========================================


class TestBatchEstimation:
    """Tests for batch request estimation."""

    def test_estimate_batch_cost(self):
        """Batch estimation aggregates correctly."""
        counter = TokenCounter()

        requests = [
            {"messages": [{"role": "user", "content": "Hello"}], "model": "claude-haiku-4-20250514"},
            {"messages": [{"role": "user", "content": "World"}], "model": "claude-haiku-4-20250514"},
        ]

        result = counter.estimate_batch_cost(requests)

        assert result["request_count"] == 2
        assert result["total_input_tokens"] > 0
        assert result["total_estimated_cost_usd"] > 0
        assert len(result["estimates"]) == 2


# ===========================================
# SINGLETON & CONVENIENCE FUNCTIONS
# ===========================================


class TestConvenienceFunctions:
    """Tests for singleton and convenience functions."""

    def test_get_token_counter_singleton(self):
        """get_token_counter returns same instance."""
        counter1 = get_token_counter()
        counter2 = get_token_counter()
        assert counter1 is counter2

    def test_count_tokens_function(self):
        """count_tokens convenience function works."""
        tokens = count_tokens("Hello, world!")
        assert tokens > 0

    def test_estimate_cost_function(self):
        """estimate_cost convenience function works."""
        cost = estimate_cost(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert cost > 0


# ===========================================
# EDGE CASES
# ===========================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_none_content_message(self):
        """Message with None content is handled."""
        counter = TokenCounter()
        messages = [{"role": "user", "content": None}]
        # Should not raise
        tokens = counter.count_message_tokens(messages)
        assert tokens >= 3  # At least overhead

    def test_multipart_content_text(self):
        """Multipart content with text parts works."""
        counter = TokenCounter()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]
        }]
        tokens = counter.count_message_tokens(messages)
        assert tokens > 5

    def test_very_long_system_prompt(self):
        """Very long system prompt is handled."""
        counter = TokenCounter()
        long_system = "You must follow these rules:\n" * 1000

        estimate = counter.estimate_request(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hello"}],
            system=long_system,
        )

        assert estimate.system_tokens > 1000
        assert estimate.context_usage_percent > 1  # Should use noticeable context
