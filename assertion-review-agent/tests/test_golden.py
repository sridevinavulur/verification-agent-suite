"""Golden-output tests over the curated good/bad corpus."""

from __future__ import annotations

from conftest import load_golden, summarize


def test_corpus_matches_golden(corpus_case):
    sva_rel, manifest_rel = corpus_case
    got = summarize(sva_rel, manifest_rel)
    want = load_golden(sva_rel)
    assert got == want, (
        f"Golden mismatch for {sva_rel}. Regenerate with scripts/regen_golden.py "
        "after confirming the change is intended."
    )


def test_good_examples_have_no_errors_or_warnings(corpus_case):
    sva_rel, _ = corpus_case
    if not sva_rel.startswith("good/"):
        return
    want = load_golden(sva_rel)
    assert want["counts"]["ERROR"] == 0
    assert want["counts"]["WARNING"] == 0
    assert want["grade"] == "A"


def test_bad_examples_have_errors(corpus_case):
    sva_rel, _ = corpus_case
    if not sva_rel.startswith("bad/"):
        return
    want = load_golden(sva_rel)
    assert want["counts"]["ERROR"] >= 1
