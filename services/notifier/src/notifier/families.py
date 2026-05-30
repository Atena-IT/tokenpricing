from __future__ import annotations

import re

_VARIANT_TOKENS = {
    "chat",
    "flash",
    "haiku",
    "instruct",
    "latest",
    "mini",
    "nano",
    "opus",
    "preview",
    "pro",
    "realtime",
    "small",
    "sonnet",
    "think",
    "thinking",
    "turbo",
}
_DATE_SUFFIX = re.compile(r"-(?:19|20)\d{2}(?:-\d{2}){1,2}$")


def derive_model_family(model_id: str, display_name: str = "") -> str:
    candidate = model_id.split("/", 1)[1] if "/" in model_id else model_id
    candidate = _DATE_SUFFIX.sub("", candidate.strip().lower())
    candidate = re.sub(r"[-_](?:preview|latest|experimental)$", "", candidate)
    tokens = [token for token in re.split(r"[-_]", candidate) if token]
    if not tokens:
        return candidate or display_name.strip().lower().replace(" ", "-")

    family_tokens: list[str] = []
    saw_version_token = False
    for token in tokens:
        if family_tokens and token in _VARIANT_TOKENS:
            break
        family_tokens.append(token)
        if any(char.isdigit() for char in token):
            saw_version_token = True
            break

    if not saw_version_token and len(family_tokens) == 1 and len(tokens) > 1:
        if tokens[1] not in _VARIANT_TOKENS:
            family_tokens.append(tokens[1])

    return "-".join(family_tokens)
