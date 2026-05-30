from notifier.families import derive_model_family


def test_derive_model_family_from_versioned_models() -> None:
    assert derive_model_family("openai/gpt-5.2") == "gpt-5.2"
    assert derive_model_family("anthropic/claude-3-opus") == "claude-3"
    assert derive_model_family("google/gemini-2.5-pro") == "gemini-2.5"
    assert derive_model_family("openai/text-embedding-3-large") == "text-embedding-3"
