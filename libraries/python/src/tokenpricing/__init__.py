"""tokenpricing - LLM token pricing library.

Public API (async):
- get_pricing(model_id, currency="USD")
- compute_cost(model_id, input_tokens, output_tokens, currency="USD")

Public API (sync):
- get_pricing_sync(model_id, currency="USD")
- compute_cost_sync(model_id, input_tokens, output_tokens, currency="USD")

Data source: LLMTracker (https://github.com/DiTo97/LLMTracker)
"""

from tokenpricing.core import (
    compute_cost,
    compute_cost_sync,
    get_pricing,
    get_pricing_sync,
)

# Version will be set by package manager
__version__ = "0.1.0"

__all__ = [
    "__version__",
    "get_pricing",
    "get_pricing_sync",
    "compute_cost",
    "compute_cost_sync",
]
