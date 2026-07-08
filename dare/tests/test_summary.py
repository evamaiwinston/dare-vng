"""Unit tests for relativize_record — the per-record RELATIVE measurement.

Pure: builds RecordSummary dataclasses directly (no engine, no network). Verifies
within-record normalization, the against (negative-mass) sum, lane selection
(context vs instruction vs none), and the all-zero / empty guards.
"""

from __future__ import annotations

import pytest

from dare.results import ChunkAttribution, RecordSummary, SourceAttribution, UnitSummary
from dare.summary import relativize_record


def _src(score: float, origin: str = "context") -> SourceAttribution:
    return SourceAttribution(
        score=score, source_text="s", chunk_id=None, doc_id=None,
        retrieval_score=None, origin=origin,
    )


def _chunk(mass: float) -> ChunkAttribution:
    return ChunkAttribution(
        chunk_id="c", positive_mass=mass, net_score=mass, n_sources=1,
        n_negative_sources=0, chunk_text="t", doc_id=None, retrieval_score=None,
    )


def _unit(text, *, context_mass, instruction_mass, chunk_masses=(), negatives=()) -> UnitSummary:
    rows = [_src(-n) for n in negatives]                 # negative rows drive `against`
    return UnitSummary(
        text=text, span=(0, len(text)),
        source_attributions=rows,
        chunk_attributions=[_chunk(m) for m in chunk_masses],
        instruction_attributions=[],
        context_mass=context_mass,
        instruction_mass=instruction_mass,
    )


def _summary(units) -> RecordSummary:
    return RecordSummary(
        record_id="rec-1", query="Q", response="R",
        whole_source_attributions=[], whole_chunk_attributions=[],
        whole_instruction_attributions=[], whole_context_mass=0.0,
        whole_instruction_mass=0.0, units=units,
    )


def test_normalization_lanes_and_against():
    summary = _summary([
        _unit("A", context_mass=2.0, instruction_mass=0.0, chunk_masses=(2.0,), negatives=(0.3,)),
        _unit("B", context_mass=0.5, instruction_mass=1.0, chunk_masses=(0.4,)),
        _unit("C", context_mass=0.0, instruction_mass=0.0),
    ])

    rels = relativize_record(summary)
    assert [r.index for r in rels] == [0, 1, 2]
    assert [r.text for r in rels] == ["A", "B", "C"]

    # strongest unit (support 2.0) normalizes to 1.0; the rest scale below it
    assert rels[0].support == 2.0
    assert rels[0].relative_strength == 1.0
    assert rels[0].against == pytest.approx(0.3)
    assert rels[0].dominant_lane == "context"

    # instruction_mass (1.0) >= strongest chunk (0.4) -> instruction lane
    assert rels[1].support == 1.5
    assert rels[1].relative_strength == pytest.approx(0.75)
    assert rels[1].dominant_lane == "instruction"

    # no positive support -> none lane, zero strength
    assert rels[2].support == 0.0
    assert rels[2].relative_strength == 0.0
    assert rels[2].dominant_lane == "none"


def test_chunk_beats_instruction_is_context_lane():
    # instruction present but a single chunk outweighs it -> context lane
    rels = relativize_record(_summary([
        _unit("A", context_mass=1.0, instruction_mass=0.5, chunk_masses=(1.0,)),
    ]))
    assert rels[0].dominant_lane == "context"


def test_instruction_ties_chunk_is_instruction_lane():
    # tie goes to instruction (>=)
    rels = relativize_record(_summary([
        _unit("A", context_mass=0.4, instruction_mass=0.4, chunk_masses=(0.4,)),
    ]))
    assert rels[0].dominant_lane == "instruction"


def test_all_zero_record_no_div_by_zero():
    rels = relativize_record(_summary([
        _unit("A", context_mass=0.0, instruction_mass=0.0),
        _unit("B", context_mass=0.0, instruction_mass=0.0),
    ]))
    assert all(r.relative_strength == 0.0 for r in rels)
    assert all(r.dominant_lane == "none" for r in rels)


def test_empty_units():
    assert relativize_record(_summary([])) == []
