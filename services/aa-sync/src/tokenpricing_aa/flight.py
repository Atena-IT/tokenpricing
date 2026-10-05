"""Extraction of the React flight payload embedded in Artificial Analysis pages.

AA is a Next.js app. Every page streams its server-rendered data into the initial
HTML document as a sequence of ``self.__next_f.push([1,"<json string>"])`` calls;
concatenating those string literals reconstructs one flight payload containing the
full dataset behind the page.

This is the *only* acquisition mechanism this service needs, because the payload is
a superset of what the page's HTML table renders:

* The rendered table shows 12 columns collapsed and 50 expanded, but "Expand
  Columns" is a client-side toggle over data that already shipped -- expanding
  issues no network request.
* The provider leaderboard renders only non-deprecated offerings (its ``Status:
  Current`` filter), while its payload carries every offering. Measured
  2026-08-14: Nebius rendered 25 of 35, Azure rendered 20 of 84, and
  ``rendered + deprecated == payload`` exactly for both.

So one GET of the leaderboard yields every offering of every provider with every
field, and the per-provider pages are redundant.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Only [1, "<string>"] chunks carry payload text; [0]/[2] chunks are framing.
_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')

# React encodes `undefined` as this sentinel string rather than omitting the key.
UNDEFINED = "$undefined"


class PayloadNotFoundError(RuntimeError):
    """The flight payload could not be located or reconstructed from a page.

    This is the failure mode to expect if AA stops shipping data in the initial
    document -- moving to a client-side fetch, a different bundler, or a
    different serialisation. It is deliberately distinct from a parse error over
    a payload that *was* found: the remedy is different.
    """


def reconstruct_payload(html: str) -> str:
    """Concatenate every flight chunk in ``html`` into one payload string."""
    literals = _CHUNK.findall(html)
    if not literals:
        raise PayloadNotFoundError(
            "no self.__next_f.push([1,...]) chunks found in the document; "
            "AA may no longer ship page data in the initial HTML"
        )
    try:
        payload = "".join(json.loads(literal) for literal in literals)
    except json.JSONDecodeError as exc:
        raise PayloadNotFoundError(
            f"flight chunks found ({len(literals)}) but a chunk is not a decodable "
            f"JSON string literal: {exc}"
        ) from exc
    if not payload.strip():
        raise PayloadNotFoundError(
            f"flight chunks found ({len(literals)}) but they reconstructed to an "
            "empty payload"
        )
    return payload


def _enclosing_object(text: str, pos: int) -> str | None:
    """Return the smallest complete JSON object containing ``pos``.

    Walks backwards to the object's opening brace, then forwards with a
    string-aware depth counter to its close.
    """
    depth = 0
    start = None
    for i in range(pos, -1, -1):
        char = text[i]
        if char == "}":
            depth += 1
        elif char == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return None

    depth = 0
    in_string = False
    escaped = False
    for j in range(start, len(text)):
        char = text[j]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def objects_with_key(payload: str, key: str) -> list[dict[str, Any]]:
    """Every JSON object in ``payload`` that carries ``key``, de-duplicated by identity.

    The payload is a flat stream rather than one document, so records are located
    by a marker key and brace-matched outwards instead of being indexed by path.
    """
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(re.escape(f'"{key}"'), payload):
        raw = _enclosing_object(payload, match.start())
        if raw is None or raw in seen:
            continue
        seen.add(raw)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            # A marker can appear inside a label dictionary or a chart config,
            # where the enclosing braces are not a self-contained object.
            continue
        if isinstance(obj, dict) and key in obj:
            found.append(obj)
    return found


def clean(value: Any) -> Any:
    """Normalise React's ``$undefined`` sentinel to ``None``, recursively.

    ``$undefined`` and an absent key mean the same thing; the leaderboard omits
    the key where a provider page emits the sentinel. Collapsing both to ``None``
    is what makes the two sources compare equal.
    """
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if v != UNDEFINED}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if value == UNDEFINED:
        return None
    return value
