"""Fixture builders that reproduce the real shape of an AA page.

Pages are built the way AA ships them -- payload text split across several
``self.__next_f.push([1,"..."])`` chunks -- so that tests exercise chunk
reconstruction rather than a convenient single-blob shortcut. Every test that needs
a *broken* page starts from one of these and damages it deliberately.
"""

from __future__ import annotations

import json
from typing import Any


def offering(**overrides: Any) -> dict[str, Any]:
    """One offering object shaped exactly like the live payload's."""
    obj: dict[str, Any] = {
        "id": "10b47ef3-f0b9-4d9e-808a-9ed9ad14e73f",
        "label": "Kimi K2.6",
        "hostApiId": "moonshotai/Kimi-K2.6",
        "footnotes": None,
        "host": {
            "name": "Nebius",
            "slug": "nebius",
            "logo": "nebius_small.svg",
            "color": "#112a40",
            "functionCallingUrl": "https://docs.nebius.com/tool-calling",
            "jsonModeUrl": "https://docs.nebius.com/json/",
        },
        "model": {
            "slug": "kimi-k2-6",
            "isOpenWeights": True,
            "deprecated": True,
            "reasoningModel": True,
            "intelligenceIndex": 45.1382483763163,
            "intelligenceIndexIsEstimated": False,
            "omniscience": 5.3,
            "omniscienceAccuracy": 0.326,
            "omniscienceNonHallucination": 0.5949554896142433,
            "briefcase": {"elo": 818.82},
            "harveyLab": 0.841221595020987,
            "automationBench": 0.19552711052930297,
            "gdpvalNormalized": 0.34519,
            "terminalbenchHard": 0.439393939393939,
            "terminalbenchV21": 0.659176029962547,
            "tau2": 0.95906432748538,
            "tauBanking": 0.232989690721649,
            "lcr": 0.766666666666667,
            "hle": 0.374884151992586,
            "gpqa": 0.911111111111111,
            "scicode": 0.534722222222222,
            "livecodebench": None,
            "aime25": None,
            "ifbench": 0.759863945578231,
            "critpt": 0.08,
            "apexAgents": 0.284660766961652,
            "itbenchSre": 0.311864406779661,
            "mmmuPro": 0.79364161849711,
            "sizeClass": "large",
            "creator": {"name": "Kimi", "logo": "kimi.jpg"},
        },
        "features": {
            "contextWindowTokens": 262144,
            "functionCalling": True,
            "jsonMode": True,
            "openaiCompatible": True,
        },
        "pricing": {
            "costPerTask": 0.7586225879503231,
            "priceClass": "high",
            "price1mInputTokens": 0.95,
            "price1mOutputTokens": 4,
            "cacheHitPrice": None,
            "cacheWritePrice": None,
        },
        "performance": {
            "medianOutputTokensPerSecond": 161.843217857469,
            "percentile05OutputTokensPerSecond": 86.2935722234904,
            "quartile25OutputTokensPerSecond": 110.732402161215,
            "quartile75OutputTokensPerSecond": 238.691468618383,
            "percentile95OutputTokensPerSecond": 330.205485545576,
            "medianTimeToFirstTokenSeconds": 1.935748112,
            "percentile05TimeToFirstTokenSeconds": 1.84192147900001,
            "quartile25TimeToFirstTokenSeconds": 1.91706955349997,
            "quartile75TimeToFirstTokenSeconds": 2.01518286099997,
            "percentile95TimeToFirstTokenSeconds": 5.47746819690005,
            "medianTimeToFirstAnswerTokenSeconds": 29.43767286932827,
            "medianEndToEndResponseTimeSeconds": 32.52708252528517,
            "medianReasoningTimeSeconds": 27.501924757328272,
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(obj.get(key), dict):
            obj[key] = {**obj[key], **value}
        else:
            obj[key] = value
    return obj


def make_page(payload_obj: Any, chunks: int = 3) -> str:
    """Render ``payload_obj`` into an HTML document, split across flight chunks."""
    text = json.dumps(payload_obj, ensure_ascii=False)
    size = max(1, len(text) // chunks + 1)
    pieces = [text[i : i + size] for i in range(0, len(text), size)]
    scripts = "".join(
        f"<script>self.__next_f.push([1,{json.dumps(piece)}])</script>"
        for piece in pieces
    )
    return (
        "<!DOCTYPE html><html><head><title>Artificial Analysis</title></head>"
        f"<body><table><thead><tr><th>Model</th></tr></thead></table>"
        f'<script>self.__next_f.push([0])</script>{scripts}</body></html>'
    )


def leaderboard_page(offerings: list[dict[str, Any]] | None = None, **kw: Any) -> str:
    objects = offerings if offerings is not None else [offering()]
    return make_page({"rsc": "payload", "data": objects}, **kw)


def openness_page(
    records: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    **kw: Any,
) -> str:
    """An Openness Index page: score records plus the model entities they point at."""
    if records is None:
        records = [
            {
                "id": "9b8adea3-ffcb-46fe-8fcf-acd121000a80",
                "modelId": "f0083258-8646-45b8-8082-7aaf6c2ea82a",
                "dataPretrainAccess": 0,
                "dataPretrainLicense": 0,
                "dataPosttrainAccess": 0,
                "dataPosttrainLicense": 0,
                "opennessIndex": 38.888888888888886,
                "modelAvailability": 6,
                "modelTransparency": 1,
                "transparencyMethodology": 1,
                "transparencyPostTrainingData": 0,
                "transparencyPreTrainingData": 0,
            }
        ]
    if entities is None:
        entities = [
            {
                "id": "f0083258-8646-45b8-8082-7aaf6c2ea82a",
                "slug": "kimi-k2-6",
                "name": "Kimi K2.6",
                "model_family_slug": "kimi-k2",
                "deprecated": False,
            }
        ]
    return make_page({"scores": records, "models": entities}, **kw)
