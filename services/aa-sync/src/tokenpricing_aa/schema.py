"""Structural and semantic drift detection against a checked-in manifest.

"The pipeline did not crash" is not evidence that the source is unchanged. A
payload can stay perfectly parseable while a field quietly disappears, flips type,
or changes units -- and a scraper that only fails on exceptions will publish the
resulting nonsense.

So the expected shape is recorded explicitly in ``schema/offering-manifest.json``
and compared against the live payload on every run. Four signals, deliberately
separated because they need different responses:

``missing``
    A field the manifest expects is gone, or has collapsed to entirely null after
    having been populated. Breaks downstream columns.
``type_changed``
    A field now carries a different JSON type. Breaks downstream columns.
``range_shifted``
    A numeric field's values have moved far outside their recorded range, which is
    how a *unit* change looks from the outside -- fractions rescaled to
    percentages, per-1M prices restated per-1k. Parses fine, means something else.
``new``
    A field appeared. Informational only: additive change is how AA ships new
    benchmarks, and it is never a reason to fail a run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tokenpricing_aa.paths import OFFERING_MANIFEST_PATH as MANIFEST_PATH

__all__ = [
    "MANIFEST_PATH",
    "RANGE_TOLERANCE",
    "DriftReport",
    "FieldSpec",
    "build_manifest",
    "check_drift",
    "flatten",
    "load_manifest",
    "type_name",
]

# A numeric field's live values may sit this many times outside the recorded
# span before it reads as a unit change rather than ordinary week-to-week drift.
RANGE_TOLERANCE = 10.0

# Below this recorded fill rate a field is too sparse for "entirely null now" to
# mean anything; several benchmarks are legitimately scored for a handful of models.
SPARSE_FIELD_THRESHOLD = 0.2


def type_name(value: Any) -> str:
    """JSON type name for ``value``. ``bool`` is checked before ``int`` deliberately."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def flatten(obj: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts to dotted paths. Leaf values only."""
    out: dict[str, Any] = {}
    for key, value in obj.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


@dataclass
class FieldSpec:
    types: set[str]
    populated_ratio: float
    minimum: float | None = None
    maximum: float | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "types": sorted(self.types),
            "populated_ratio": round(self.populated_ratio, 4),
        }
        if self.minimum is not None:
            out["minimum"] = self.minimum
        if self.maximum is not None:
            out["maximum"] = self.maximum
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> FieldSpec:
        return cls(
            types=set(data["types"]),
            populated_ratio=float(data.get("populated_ratio", 0.0)),
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
        )


@dataclass
class DriftReport:
    missing: list[str] = field(default_factory=list)
    type_changed: list[str] = field(default_factory=list)
    range_shifted: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    record_count: int = 0

    @property
    def breaking(self) -> bool:
        """New fields are additive and do not make a report breaking."""
        return bool(self.missing or self.type_changed or self.range_shifted)

    def summary(self) -> str:
        if not self.breaking and not self.new:
            return f"no drift over {self.record_count} records"
        parts = []
        for label, items in (
            ("missing", self.missing),
            ("type changed", self.type_changed),
            ("range shifted", self.range_shifted),
            ("new", self.new),
        ):
            if items:
                parts.append(f"{label}: {', '.join(sorted(items))}")
        return " | ".join(parts)


def build_manifest(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive a manifest from live payload objects."""
    flats = [flatten(obj) for obj in objects]
    paths: set[str] = set()
    for flat in flats:
        paths |= set(flat)

    specs: dict[str, FieldSpec] = {}
    for path in sorted(paths):
        types: set[str] = set()
        populated = 0
        numbers: list[float] = []
        for flat in flats:
            if path not in flat:
                continue
            value = flat[path]
            types.add(type_name(value))
            if value is not None:
                populated += 1
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numbers.append(float(value))
        spec = FieldSpec(
            types=types,
            populated_ratio=populated / len(flats) if flats else 0.0,
        )
        if numbers:
            spec.minimum = min(numbers)
            spec.maximum = max(numbers)
        specs[path] = spec

    return {
        "record_count": len(objects),
        "fields": {path: spec.to_json() for path, spec in specs.items()},
    }


def load_manifest(path: Path | None = None) -> dict[str, FieldSpec]:
    data = json.loads((path or MANIFEST_PATH).read_text(encoding="utf-8"))
    return {p: FieldSpec.from_json(s) for p, s in data["fields"].items()}


def check_drift(
    objects: list[dict[str, Any]], manifest: dict[str, FieldSpec] | None = None
) -> DriftReport:
    """Compare live payload objects against the expected manifest."""
    expected = manifest if manifest is not None else load_manifest()
    flats = [flatten(obj) for obj in objects]
    report = DriftReport(record_count=len(flats))
    if not flats:
        report.missing = sorted(expected)
        return report

    observed: dict[str, list[Any]] = {}
    for flat in flats:
        for path, value in flat.items():
            observed.setdefault(path, []).append(value)

    for path, spec in expected.items():
        values = observed.get(path)
        if values is None:
            report.missing.append(path)
            continue

        non_null = [v for v in values if v is not None]
        if (
            not non_null
            and spec.populated_ratio >= SPARSE_FIELD_THRESHOLD
        ):
            report.missing.append(f"{path} (present but entirely null)")
            continue

        live_types = {type_name(v) for v in non_null}
        unexpected = live_types - spec.types
        if unexpected:
            report.type_changed.append(
                f"{path} ({'/'.join(sorted(unexpected))} not in "
                f"{'/'.join(sorted(spec.types))})"
            )
            continue

        if spec.minimum is not None and spec.maximum is not None:
            numbers = [
                float(v) for v in non_null if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            if numbers:
                span = max(abs(spec.maximum - spec.minimum), 1e-9)
                allowance = span * RANGE_TOLERANCE
                low = spec.minimum - allowance
                high = spec.maximum + allowance
                if min(numbers) < low or max(numbers) > high:
                    report.range_shifted.append(
                        f"{path} (observed {min(numbers):.4g}..{max(numbers):.4g}, "
                        f"expected within {low:.4g}..{high:.4g})"
                    )

    for path in sorted(set(observed) - set(expected)):
        report.new.append(path)

    return report
