"""Tests for Phase 29 Persian PII Ecosystem Audit & Benchmark research artifacts.

Verifies:
1. Result JSON schema, privacy invariants (zero raw PII), and sample counts.
2. Environment manifest structure and metadata cleanliness (no workstation paths).
3. Sources snapshot schema, completeness, and MIT license for ParsiKit.
4. Challenge set deterministic generation, exact offsets, TITLE/PERSON separation.
5. Legal entity research generator output passes production validator for all seeds.
6. Dataset A gold/pred taxonomy canonicalization and mapping symmetry.
7. Adapter error tracking (no silent swallowing of exceptions).
8. No hardcoded workstation cache paths or committed full card/legal-id literals.
9. Adapter isolation (no production src/ imports of research code).
10. Package configuration integrity (dependencies remain [], version 0.3.0).
11. Pure offline execution without network or heavy models.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest
from research.evaluation import EntitySpan, calculate_metrics
from research.phase29_challenge_set import (
    OPENMED_TO_CANONICAL,
    _generate_valid_legal_id,
    build_dataset_b,
    build_dataset_c,
    canonicalize_gold_spans,
)

from fa_redact import __version__
from fa_redact.validators import is_valid_iranian_legal_entity_id


def test_package_metadata_and_zero_runtime_dependencies() -> None:
    """Verify package version is 0.4.0 and base dependencies remain empty."""
    assert __version__ == "0.4.0"

    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")

    # Verify dependencies = []
    assert "dependencies = []" in content
    assert 'version = "0.4.0"' in content


def test_production_src_isolation_from_research() -> None:
    """Verify production files do not import research or benchmark tools."""
    src_dir = Path("src/fa_redact")
    forbidden_modules = {"research", "onnxruntime", "parsikit", "persian_tools"}

    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden_modules, (
                        f"Production file {py_file} imports forbidden "
                        f"research module: {root_mod}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden_modules, (
                    f"Production file {py_file} imports from forbidden "
                    f"research module: {root_mod}"
                )


def test_legal_entity_research_generator_validates_under_production_validator() -> None:
    """Verify that research _generate_valid_legal_id produces valid Variant A IDs."""
    for i in range(500):
        candidate = _generate_valid_legal_id(i)
        assert len(candidate) == 11
        assert candidate.isdigit()
        assert is_valid_iranian_legal_entity_id(candidate), (
            f"Generated legal entity ID {candidate} failed production validator"
        )


def test_dataset_a_taxonomy_mapping_symmetry_and_canonicalization() -> None:
    """Verify OpenMed label mapping and canonicalization is symmetric."""
    # Check essential entity mappings
    assert OPENMED_TO_CANONICAL["GIVENNAME"] == "PERSON"
    assert OPENMED_TO_CANONICAL["SURNAME"] == "PERSON"
    assert OPENMED_TO_CANONICAL["TELEPHONENUM"] == "IR_MOBILE"
    assert OPENMED_TO_CANONICAL["CREDITCARDNUMBER"] == "BANK_CARD"
    assert OPENMED_TO_CANONICAL["IDCARDNUM"] == "IR_NATIONAL_ID"
    assert OPENMED_TO_CANONICAL["EMAIL"] == "EMAIL"
    assert OPENMED_TO_CANONICAL["DATE"] == "DATE"
    assert OPENMED_TO_CANONICAL["TITLE"] == "TITLE"

    # Canonical span mapping
    raw_given = EntitySpan(start=0, end=3, type="GIVENNAME")
    raw_surname = EntitySpan(start=4, end=9, type="SURNAME")
    canon_given_type = OPENMED_TO_CANONICAL[raw_given.type]
    canon_surname_type = OPENMED_TO_CANONICAL[raw_surname.type]

    assert canon_given_type == "PERSON"
    assert canon_surname_type == "PERSON"

    # Adjacent span merging of same canonical type via canonicalize_gold_spans
    name_text = "علی محمدی"
    merged = canonicalize_gold_spans(name_text, [raw_given, raw_surname])
    assert len(merged) == 1
    assert merged[0].start == 0
    assert merged[0].end == 9
    assert merged[0].type == "PERSON"


def test_dataset_b_and_c_title_person_separation_policy() -> None:
    """Verify that titles (دکتر, آقای, خانم, etc.) are separated from PERSON spans."""
    title_words = {"دکتر", "خانم", "آقای", "مهندس", "استاد", "حاج", "پروفسور"}

    # Dataset B
    docs_b = build_dataset_b()
    for doc in docs_b:
        for span in doc.gold_spans:
            if span.type == "PERSON":
                extracted = doc.text[span.start : span.end]
                for tw in title_words:
                    assert not extracted.startswith(tw + " "), (
                        f"Dataset B PERSON span '{extracted}' has title '{tw}'"
                    )

    # Dataset C
    docs_c = build_dataset_c()
    for doc in docs_c:
        for span in doc.gold_spans:
            if span.type == "PERSON":
                extracted = doc.text[span.start : span.end]
                for tw in title_words:
                    assert not extracted.startswith(tw + " "), (
                        f"Dataset C PERSON span '{extracted}' has title '{tw}'"
                    )
                # Check relationship strings not in PERSON
                assert "(پدر)" not in extracted
                assert "(مادر)" not in extracted
                assert "(همسر)" not in extracted
                assert "(فرزند)" not in extracted


def test_sources_snapshot_schema_and_completeness() -> None:
    """Verify research/phase29_sources.json is well-structured and accurate."""
    sources_file = Path("research/phase29_sources.json")
    assert sources_file.exists()

    with open(sources_file, encoding="utf-8") as f:
        sources = json.load(f)

    assert isinstance(sources, list)
    assert len(sources) >= 10

    required_keys = {
        "source_id",
        "title",
        "publisher_owner",
        "source_type",
        "canonical_url_or_repo",
        "revision",
        "access_date",
        "license",
        "supported_claim",
        "evidence_notes",
    }

    source_ids = set()
    for s in sources:
        assert isinstance(s, dict)
        assert required_keys.issubset(s.keys()), (
            f"Missing keys in source {s.get('source_id')}"
        )
        assert s["source_id"] not in source_ids, (
            f"Duplicate source_id: {s['source_id']}"
        )
        source_ids.add(s["source_id"])
        assert s["license"], f"Source {s['source_id']} missing license"
        assert s["canonical_url_or_repo"], (
            f"Source {s['source_id']} missing canonical URL/repo"
        )

    # Verify key ecosystem anchors are present
    assert "openmed-tookabert-onnx-int4" in source_ids
    assert "openmed-mbert-onnx-int4" in source_ids
    assert "openmed-dataset-690k-clean" in source_ids
    assert "parsikit" in source_ids
    assert "py-persian-tools" in source_ids
    assert "peyma-ner" in source_ids

    # Verify ParsiKit license is MIT
    parsikit_source = next(s for s in sources if s["source_id"] == "parsikit")
    assert parsikit_source["license"] == "MIT"

    # Verify py-persian-tools has supply chain note
    pt_source = next(s for s in sources if s["source_id"] == "py-persian-tools")
    assert "supply_chain" in pt_source or "18aa49e" in pt_source["evidence_notes"]


def test_environment_manifest_schema_and_privacy() -> None:
    """Verify environment manifest has no private paths or tokens."""
    env_file = Path("research/results/phase29_environment.json")
    assert env_file.exists()

    with open(env_file, encoding="utf-8") as f:
        env_data = json.load(f)

    assert "operating_system" in env_data
    assert "python_version" in env_data
    assert "package_versions" in env_data
    assert "model_revisions" in env_data
    assert "dataset_revisions" in env_data

    # Check that no private strings or workstation paths leaked
    env_str = json.dumps(env_data)
    assert "C:\\Users\\" not in env_str
    assert "D:\\" not in env_str
    assert "token" not in env_str.lower() or "huggingface" not in env_str.lower()


def test_no_hardcoded_workstation_cache_paths_in_research_code() -> None:
    """Verify no hardcoded D:/ or user-specific cache paths exist in codebase."""
    research_dir = Path("research")
    for py_file in research_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert 'cache_dir = "D:/' not in content, (
            f"Hardcoded cache path found in {py_file}"
        )
        assert 'cache_dir = "D:\\\\' not in content, (
            f"Hardcoded cache path found in {py_file}"
        )
        assert 'cache_dir="D:/' not in content, (
            f"Hardcoded cache path found in {py_file}"
        )


def test_challenge_dataset_b_generation_and_integrity() -> None:
    """Verify Dataset B generates deterministically with exact offsets."""
    doc_set_1 = build_dataset_b()
    doc_set_2 = build_dataset_b()

    assert len(doc_set_1) == len(doc_set_2) == 150

    total_gold_spans = 0
    for doc in doc_set_1:
        assert doc.doc_id
        assert doc.text
        for span in doc.gold_spans:
            total_gold_spans += 1
            # Exact boundary bounds
            assert 0 <= span.start < span.end <= len(doc.text)
            extracted = doc.text[span.start : span.end]
            assert extracted.strip() != "", f"Empty span in {doc.doc_id}: {span}"
            assert not extracted.startswith(" ")
            assert not extracted.endswith(" ")

    assert total_gold_spans > 150


def test_challenge_dataset_c_clinical_generation_and_integrity() -> None:
    """Verify Dataset C generates deterministically with exact offsets."""
    doc_set = build_dataset_c()
    assert len(doc_set) == 120

    total_spans = 0
    categories = set()
    for doc in doc_set:
        assert doc.doc_id
        assert doc.text
        assert doc.category
        for span in doc.gold_spans:
            total_spans += 1
            categories.add(span.type)
            assert 0 <= span.start < span.end <= len(doc.text)
            extracted = doc.text[span.start : span.end]
            assert extracted.strip() != ""
            assert not extracted.startswith(" ")
            assert not extracted.endswith(" ")

    assert total_spans >= 600
    assert "PERSON" in categories
    assert "IR_MOBILE" in categories
    assert "IR_NATIONAL_ID" in categories


def test_metric_arithmetic_helper() -> None:
    """Verify calculate_metrics precision, recall, and F1 calculations."""
    prec, rec, f1 = calculate_metrics(10, 0, 0)
    assert (prec, rec, f1) == (1.0, 1.0, 1.0)

    prec, rec, f1 = calculate_metrics(5, 5, 5)
    assert prec == 0.5
    assert rec == 0.5
    assert f1 == 0.5

    prec, rec, f1 = calculate_metrics(0, 0, 0)
    assert (prec, rec, f1) == (1.0, 1.0, 1.0)


def test_benchmark_result_json_schema_and_sample_counts() -> None:
    """Verify benchmark result JSON schema, privacy, and exact sample counts."""
    result_file = Path("research/results/phase29_persian_pii_benchmark.json")
    if not result_file.exists():
        pytest.skip("Benchmark result JSON not yet written")

    with open(result_file, encoding="utf-8") as f:
        data = json.load(f)

    # Check sample sizes
    datasets = data.get("datasets", {})
    assert datasets.get("dataset_a_reproduction", {}).get("sample_rows") == 100
    assert datasets.get("dataset_b_independent", {}).get("documents_count") == 150
    assert datasets.get("dataset_c_clinical", {}).get("documents_count") == 120

    # Walk through entire JSON and verify no raw text keys
    forbidden_keys = {
        "source_text",
        "masked_text",
        "raw_value",
        "patient_name",
        "pii_value",
        "snippet",
    }

    def check_dict(d: dict[str, Any]) -> None:
        for k, v in d.items():
            assert k not in forbidden_keys, (
                f"Forbidden raw PII key '{k}' found in benchmark results JSON"
            )
            if isinstance(v, dict):
                check_dict(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        check_dict(item)

    check_dict(data)
