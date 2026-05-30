from notifier.webhooks import MAX_ERROR_LENGTH, _truncate_error


def test_truncate_error_bounds_large_payloads() -> None:
    message = "x" * (MAX_ERROR_LENGTH + 10)

    truncated = _truncate_error(message)

    assert truncated == f"{'x' * MAX_ERROR_LENGTH}..."
