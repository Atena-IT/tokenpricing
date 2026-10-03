"""Dataset assembly and the shape guards that stop a thin capture publishing."""

from __future__ import annotations

import pytest

from tests.factories import leaderboard_page, offering, openness_page
from tokenpricing_aa.normalize import ShapeError, normalize_sources
from tokenpricing_aa.schema import DriftReport


def _capture(page: str, url: str = "https://artificialanalysis.ai/leaderboards/providers"):
    return {"source_url": url, "fetched_at": "2026-08-14T09:00:00+00:00", "page": page}


def _wide_payload(providers: int = 50, per_provider: int = 20):
    """A capture big enough to clear the shape guards."""
    objects = []
    for p in range(providers):
        for m in range(per_provider):
            objects.append(
                offering(
                    id=f"off-{p}-{m}",
                    label=f"Model {m}",
                    host={"slug": f"provider-{p}", "name": f"Provider {p}"},
                    model={"slug": f"model-{m}"},
                )
            )
    return objects


def _build(objects, openness_html=None, drift=None):
    return normalize_sources(
        _capture(leaderboard_page(objects)),
        _capture(openness_html or _wide_openness(), url="https://artificialanalysis.ai/o"),
        drift=drift or DriftReport(record_count=len(objects)),
    )


def _wide_openness(count: int = 300):
    records, entities = [], []
    for i in range(count):
        records.append(
            {
                "id": f"score-{i}",
                "modelId": f"model-uuid-{i}",
                "opennessIndex": 38.0 + (i % 10),
                "modelAvailability": 6,
                "modelTransparency": 1,
                "dataPretrainAccess": 0,
                "dataPretrainLicense": 0,
                "dataPosttrainAccess": 0,
                "dataPosttrainLicense": 0,
                "transparencyMethodology": 1,
                "transparencyPreTrainingData": 0,
                "transparencyPostTrainingData": 0,
            }
        )
        entities.append(
            {"id": f"model-uuid-{i}", "slug": f"model-{i}", "name": f"Model {i}"}
        )
    return openness_page(records, entities)


def test_builds_a_dataset_from_a_healthy_capture():
    dataset = _build(_wide_payload())
    assert dataset.metadata.offering_count == 1000
    assert dataset.metadata.provider_count == 50
    assert dataset.metadata.openness_row_count == 300


def test_deprecated_offerings_are_kept_and_counted():
    """Superseded rows are the whole reason the payload beats the rendered table."""
    objects = _wide_payload()
    objects[0]["model"]["deprecated"] = False
    dataset = _build(objects)
    assert dataset.metadata.deprecated_offering_count == 999
    assert any(o.deprecated for o in dataset.offerings)
    assert any(not o.deprecated for o in dataset.offerings)


def test_offering_id_is_carried_onto_every_row():
    dataset = _build(_wide_payload())
    ids = {o.offering_id for o in dataset.offerings}
    assert len(ids) == len(dataset.offerings)


def test_openness_breakdown_is_attached_by_slug():
    dataset = _build(_wide_payload(providers=50, per_provider=20))
    scored = [o for o in dataset.offerings if o.openness is not None]
    assert scored, "model-N slugs should match openness entities of the same slug"
    assert scored[0].openness.openness_index is not None


def test_reasoning_variant_is_recorded():
    objects = _wide_payload()
    objects[0]["label"] = "Claude Opus 5 (max)"
    objects[0]["model"]["slug"] = "claude-opus-5"
    objects[1]["model"]["slug"] = "claude-opus-5-low"
    dataset = _build(objects)
    by_slug = {o.model_slug: o for o in dataset.offerings}
    assert by_slug["claude-opus-5"].reasoning_effort == "max"
    assert by_slug["claude-opus-5-low"].reasoning_effort == "low"
    assert by_slug["claude-opus-5"].reasoning_mode == "reasoning"


def test_drift_summary_is_recorded_in_metadata():
    report = DriftReport(record_count=1000, new=["model.newBench"])
    dataset = _build(_wide_payload(), drift=report)
    assert dataset.metadata.drift.new == ["model.newBench"]
    assert dataset.metadata.drift.breaking is False


# --- shape guards ---------------------------------------------------------- #


def test_too_few_offerings_is_rejected():
    with pytest.raises(ShapeError, match="offerings parsed"):
        _build(_wide_payload(providers=5, per_provider=5))


def test_too_few_providers_is_rejected():
    with pytest.raises(ShapeError, match="providers in the payload"):
        _build(_wide_payload(providers=10, per_provider=100))


def test_duplicate_offering_ids_are_rejected():
    """The primary key must be verified, not assumed."""
    objects = _wide_payload()
    objects[1]["id"] = objects[0]["id"]
    with pytest.raises(ShapeError, match="offering_id is not unique"):
        _build(objects)


def test_missing_model_slugs_are_rejected():
    objects = _wide_payload()
    for obj in objects[:200]:
        obj["model"]["slug"] = None
    with pytest.raises(ShapeError, match="carry a model slug"):
        _build(objects)


def test_too_few_openness_rows_is_rejected():
    with pytest.raises(ShapeError, match="openness rows parsed"):
        _build(_wide_payload(), openness_html=_wide_openness(count=10))


def test_sources_are_recorded_for_attribution():
    dataset = _build(_wide_payload())
    assert dataset.metadata.sources == [
        "https://artificialanalysis.ai/leaderboards/providers",
        "https://artificialanalysis.ai/o",
    ]
    assert "Artificial Analysis" in dataset.metadata.attribution
