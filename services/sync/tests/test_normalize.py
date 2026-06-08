from tokenpricing_sync.normalize import normalize_sources


def test_normalize_sources_preserves_cache_fields() -> None:
    openrouter = {
        "fetched_at": "2026-06-08T00:00:00+00:00",
        "data": {
            "data": [
                {
                    "id": "openai/gpt-5.2",
                    "name": "GPT-5.2",
                    "pricing": {
                        "prompt": "0.000002",
                        "completion": "0.000006",
                        "input_cache_read": "0.000001",
                        "input_cache_write": "0.000003",
                    },
                    "context_length": 128000,
                    "supported_parameters": ["tools"],
                    "top_provider": {"max_completion_tokens": 8192},
                }
            ]
        },
    }
    litellm = {
        "fetched_at": "2026-06-08T00:00:00+00:00",
        "data": {
            "openai/gpt-5.2": {
                "input_cost_per_token": 0.000002,
                "output_cost_per_token": 0.000006,
                "cache_read_input_token_cost": 0.000001,
                "cache_creation_input_token_cost": 0.000003,
                "max_input_tokens": 128000,
                "max_output_tokens": 8192,
                "mode": "chat",
                "supports_function_calling": True,
            }
        },
    }

    dataset = normalize_sources(openrouter, litellm)
    model = dataset.models["openai/gpt-5.2"]

    assert model.pricing.input_per_million == 2.0
    assert model.pricing.output_per_million == 6.0
    assert model.pricing.cache_read_per_million == 1.0
    assert model.pricing.cache_creation_per_million == 3.0
    assert model.model_type == "chat"
