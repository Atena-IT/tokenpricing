from tokenpricing_sync.fetch import _wrap_source_payload


def test_wrap_source_payload_flattens_openrouter_shape() -> None:
    payload = _wrap_source_payload(
        "openrouter",
        "https://openrouter.ai/api/v1/models",
        {"data": [{"id": "openai/gpt-5"}]},
    )

    assert payload["api_url"] == "https://openrouter.ai/api/v1/models"
    assert "source_url" not in payload
    assert payload["model_count"] == 1
    assert payload["data"] == [{"id": "openai/gpt-5"}]


def test_wrap_source_payload_preserves_other_source_shape() -> None:
    payload = _wrap_source_payload(
        "litellm",
        "https://example.com/litellm.json",
        {"openai/gpt-5": {"input_cost_per_token": 0.000001}},
    )

    assert payload["source_url"] == "https://example.com/litellm.json"
    assert payload["model_count"] == 1
    assert payload["data"] == {"openai/gpt-5": {"input_cost_per_token": 0.000001}}
