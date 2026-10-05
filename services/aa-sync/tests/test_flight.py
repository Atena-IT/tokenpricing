"""Flight payload extraction, including the "AA changed how it ships data" mode."""

from __future__ import annotations

import json

import pytest

from tests.factories import leaderboard_page, make_page, offering
from tokenpricing_aa.flight import (
    UNDEFINED,
    PayloadNotFoundError,
    clean,
    objects_with_key,
    reconstruct_payload,
)


def test_reconstructs_payload_across_chunk_boundaries():
    html = leaderboard_page(chunks=7)
    payload = reconstruct_payload(html)
    assert '"hostApiId"' in payload
    # Reconstruction must be lossless: the joined text parses as the original.
    assert json.loads(payload)["data"][0]["label"] == "Kimi K2.6"


def test_finds_offering_objects_in_a_flat_payload_stream():
    html = leaderboard_page([offering(id="a"), offering(id="b", label="Other")])
    objects = objects_with_key(reconstruct_payload(html), "hostApiId")
    assert {o["id"] for o in objects} == {"a", "b"}


def test_ignores_marker_occurrences_that_are_not_self_contained_objects():
    # A label dictionary mentioning the marker key must not become a record.
    html = make_page(
        {
            "labels": {"hostApiId": "API ID", "price": "Price"},
            "data": [offering(id="real")],
        }
    )
    objects = objects_with_key(reconstruct_payload(html), "hostApiId")
    ids = [o.get("id") for o in objects]
    assert "real" in ids


# --- failure mode 1: the payload is no longer there ------------------------- #


def test_missing_flight_chunks_raise_payload_not_found():
    html = "<html><body><table><tr><td>rendered but no payload</td></tr></table></body></html>"
    with pytest.raises(PayloadNotFoundError, match="no self.__next_f.push"):
        reconstruct_payload(html)


def test_chunks_present_but_undecodable_raise_payload_not_found():
    # Chunk syntax survives, contents do not: a bundler/serialisation change.
    html = '<script>self.__next_f.push([1,"\\uZZZZ"])</script>'
    with pytest.raises(PayloadNotFoundError):
        reconstruct_payload(html)


def test_chunks_that_reconstruct_to_nothing_raise_payload_not_found():
    html = '<script>self.__next_f.push([1,"   "])</script>'
    with pytest.raises(PayloadNotFoundError, match="empty payload"):
        reconstruct_payload(html)


def test_client_side_fetch_migration_looks_like_a_missing_payload():
    # The realistic future break: data arrives by XHR, HTML ships only the shell.
    html = (
        "<html><body><div id='root'></div>"
        "<script>fetch('/api/leaderboard').then(r=>r.json())</script>"
        "</body></html>"
    )
    with pytest.raises(PayloadNotFoundError):
        reconstruct_payload(html)


# --- the $undefined sentinel ----------------------------------------------- #


def test_clean_collapses_the_undefined_sentinel_to_none():
    assert clean({"a": UNDEFINED, "b": 1}) == {"b": 1}
    assert clean({"n": {"deep": UNDEFINED}}) == {"n": {}}
    assert clean([UNDEFINED, 2]) == [None, 2]


def test_sentinel_and_absent_key_normalise_the_same_way():
    """Why the two sources compared equal: one omits the key, one sends $undefined."""
    with_sentinel = clean({"pricing": {"costPerTask": UNDEFINED, "priceClass": "high"}})
    without_key = clean({"pricing": {"priceClass": "high"}})
    assert with_sentinel == without_key
