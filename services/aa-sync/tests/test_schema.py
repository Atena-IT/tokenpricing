"""Drift detection: the check that a parseable payload still means what it did."""

from __future__ import annotations

import json

from tests.factories import offering
from tokenpricing_aa.parse import OFFERING_FIELDS
from tokenpricing_aa.paths import OFFERING_MANIFEST_PATH
from tokenpricing_aa.schema import (
    build_manifest,
    check_drift,
    flatten,
    load_manifest,
    type_name,
)


def _manifest(objects):
    """A manifest as specs, the way check_drift consumes it."""
    from tokenpricing_aa.schema import FieldSpec

    data = build_manifest(objects)
    return {p: FieldSpec.from_json(s) for p, s in data["fields"].items()}


def _baseline(count: int = 5):
    """Several objects so populated_ratio is meaningful."""
    return [offering(id=f"id-{i}") for i in range(count)]


def test_type_name_distinguishes_bool_from_number():
    """bool is an int subclass in Python; a silent bool->number change must not pass."""
    assert type_name(True) == "bool"
    assert type_name(1) == "number"
    assert type_name(1.5) == "number"
    assert type_name(None) == "null"
    assert type_name("x") == "string"


def test_flatten_produces_dotted_leaf_paths():
    flat = flatten(offering())
    assert flat["model.briefcase.elo"] == 818.82
    assert flat["host.slug"] == "nebius"
    assert "model" not in flat


def test_identical_payload_reports_no_drift():
    objects = _baseline()
    report = check_drift(objects, _manifest(objects))
    assert not report.breaking
    assert report.new == []
    assert "no drift" in report.summary()


# --- failure mode 3a: a field disappears ----------------------------------- #


def test_removed_field_is_flagged_missing():
    manifest = _manifest(_baseline())
    broken = []
    for i in range(5):
        obj = offering(id=f"id-{i}")
        del obj["pricing"]["price1mInputTokens"]
        broken.append(obj)
    report = check_drift(broken, manifest)
    assert report.breaking
    assert "pricing.price1mInputTokens" in report.missing


def test_field_that_went_entirely_null_is_flagged_missing():
    """Present but never populated is as broken as absent, for a populated field."""
    manifest = _manifest(_baseline())
    broken = [
        offering(id=f"id-{i}", pricing={"price1mInputTokens": None}) for i in range(5)
    ]
    report = check_drift(broken, manifest)
    assert report.breaking
    assert any("price1mInputTokens" in m for m in report.missing)


def test_sparse_field_going_null_is_not_flagged():
    """Benchmarks scored for a handful of models must not cause weekly false alarms."""
    baseline = [
        offering(id=f"id-{i}", model={"livecodebench": 0.5 if i == 0 else None})
        for i in range(10)
    ]
    manifest = _manifest(baseline)
    live = [offering(id=f"id-{i}", model={"livecodebench": None}) for i in range(10)]
    report = check_drift(live, manifest)
    assert not any("livecodebench" in m for m in report.missing)


# --- failure mode 3b: a field changes type --------------------------------- #


def test_type_change_is_flagged():
    manifest = _manifest(_baseline())
    broken = [
        offering(id=f"id-{i}", features={"contextWindowTokens": "262k"})
        for i in range(5)
    ]
    report = check_drift(broken, manifest)
    assert report.breaking
    assert any("features.contextWindowTokens" in t for t in report.type_changed)
    assert any("string" in t for t in report.type_changed)


def test_boolean_becoming_numeric_is_flagged():
    manifest = _manifest(_baseline())
    broken = [offering(id=f"id-{i}", features={"functionCalling": 1}) for i in range(5)]
    report = check_drift(broken, manifest)
    assert report.breaking
    assert any("features.functionCalling" in t for t in report.type_changed)


# --- failure mode 3c: meaning changes while the type stays ------------------ #


def test_unit_rescale_is_flagged_as_a_range_shift():
    """0-1 fractions restated as 0-100 percentages parse perfectly and mean something else."""
    baseline = [offering(id=f"id-{i}", model={"gpqa": 0.5 + i / 100}) for i in range(10)]
    manifest = _manifest(baseline)
    live = [offering(id=f"id-{i}", model={"gpqa": 50.0 + i}) for i in range(10)]
    report = check_drift(live, manifest)
    assert report.breaking
    assert any("model.gpqa" in r for r in report.range_shifted)


def test_price_restated_per_1k_is_flagged_as_a_range_shift():
    baseline = [
        offering(id=f"id-{i}", pricing={"price1mOutputTokens": 4.0 + i}) for i in range(10)
    ]
    manifest = _manifest(baseline)
    live = [
        offering(id=f"id-{i}", pricing={"price1mOutputTokens": 4000.0 + i})
        for i in range(10)
    ]
    report = check_drift(live, manifest)
    assert report.breaking
    assert any("price1mOutputTokens" in r for r in report.range_shifted)


def test_ordinary_week_to_week_movement_is_not_a_range_shift():
    baseline = [offering(id=f"id-{i}", model={"gpqa": 0.5 + i / 100}) for i in range(10)]
    manifest = _manifest(baseline)
    live = [offering(id=f"id-{i}", model={"gpqa": 0.42 + i / 50}) for i in range(10)]
    report = check_drift(live, manifest)
    assert not report.range_shifted


# --- additive change is not a failure -------------------------------------- #


def test_new_field_is_reported_but_not_breaking():
    manifest = _manifest(_baseline())
    live = [offering(id=f"id-{i}", model={"brandNewBench2027": 0.4}) for i in range(5)]
    report = check_drift(live, manifest)
    assert not report.breaking
    assert "model.brandNewBench2027" in report.new


def test_empty_payload_reports_everything_missing():
    manifest = _manifest(_baseline())
    report = check_drift([], manifest)
    assert report.breaking
    assert len(report.missing) == len(manifest)


# --- the checked-in manifest ----------------------------------------------- #


def test_checked_in_manifest_is_loadable():
    specs = load_manifest()
    assert len(specs) > 50
    assert all(spec.types for spec in specs.values())


def test_checked_in_manifest_covers_every_projected_field():
    """The projection and the manifest cannot drift apart silently."""
    specs = load_manifest()
    for _name, path in OFFERING_FIELDS:
        assert ".".join(path) in specs, f"{'.'.join(path)} not covered by the manifest"


def test_checked_in_manifest_records_the_capture_it_came_from():
    data = json.loads(OFFERING_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["record_count"] > 800
