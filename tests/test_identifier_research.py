"""Tests for Phase 27 identifier research, decision artifacts, and reference algorithms.

Ensures research artifacts conform strictly to schemas, invariants, determinism,
isolation rules, privacy guards against committed real IDs, and that no production
code or dependencies were altered.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from research.legal_entity_id_reference import (
    compare_checksum_variants,
    compute_legal_entity_checksum_variant_a,
    verify_legal_entity_id_variant_a,
    verify_legal_entity_id_variant_b,
    verify_legal_entity_id_variant_c,
    verify_legal_entity_id_variant_d,
)

import fa_redact
from fa_redact.detectors.iranian_iban import IranianIBANDetector
from fa_redact.detectors.mobile import IranianMobileNumberDetector
from fa_redact.detectors.national_id import IranianNationalIDDetector
from fa_redact.pipeline import _DEFAULT_DETECTORS

_VALID_DECISIONS = {"GO", "CONDITIONAL GO", "HOLD", "NO-GO"}
_VALID_INTEGRATIONS = {
    "DEFAULT DETECTOR",
    "OPT-IN DETECTOR",
    "PATTERN RULE",
    "VALIDATOR ONLY",
    "RESEARCH ONLY",
    "NONE",
}


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture
def research_doc_path(repo_root: Path) -> Path:
    return repo_root / "research" / "phase27_additional_iranian_identifiers.md"


@pytest.fixture
def decision_json_path(repo_root: Path) -> Path:
    return repo_root / "research" / "results" / "phase27_identifier_decision.json"


@pytest.fixture
def decision_data(decision_json_path: Path) -> dict[str, Any]:
    with open(decision_json_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


class TestDecisionJsonSchema:
    """Validate structure, constraints, and privacy of decision JSON artifact."""

    def test_top_level_schema(self, decision_data: dict[str, Any]) -> None:
        assert decision_data["schema_version"] == 1
        assert decision_data["phase"] == 27
        assert isinstance(decision_data["candidates"], list)
        assert len(decision_data["candidates"]) == 4

    def test_candidate_entries(self, decision_data: dict[str, Any]) -> None:
        candidate_ids = [c["id"] for c in decision_data["candidates"]]
        assert len(candidate_ids) == len(set(candidate_ids)), (
            "Candidate IDs must be unique"
        )
        assert candidate_ids == sorted(candidate_ids), (
            "Candidates must be deterministically sorted"
        )

        for candidate in decision_data["candidates"]:
            assert isinstance(candidate["id"], str)
            assert isinstance(candidate["name_en"], str)
            assert isinstance(candidate["name_fa"], str)
            assert candidate["decision"] in _VALID_DECISIONS
            assert candidate["recommended_integration"] in _VALID_INTEGRATIONS
            assert 0 <= candidate["score"] <= candidate["max_score"] <= 16
            assert isinstance(candidate["hard_blockers"], list)
            assert all(isinstance(b, str) for b in candidate["hard_blockers"])

            # Evidence counts
            evidence = candidate["evidence_counts"]
            assert isinstance(evidence, dict)
            assert evidence["primary"] >= 0
            assert evidence["secondary_technical"] >= 0
            assert evidence["community"] >= 0

            # Rubric scores
            rubric = candidate["rubric_scores"]
            assert isinstance(rubric, dict)
            assert sum(rubric.values()) == candidate["score"]
            for score in rubric.values():
                assert 0 <= score <= 2

    def test_deterministic_json_formatting(
        self, decision_json_path: Path, decision_data: dict[str, Any]
    ) -> None:
        """Verify that serializing produces exact byte-for-byte identical output."""
        raw_committed = decision_json_path.read_text(encoding="utf-8")
        reproduced = (
            json.dumps(decision_data, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        )
        assert raw_committed == reproduced

    def test_no_sensitive_data_leakage(self, decision_json_path: Path) -> None:
        """Verify the JSON contains no timestamps, machine paths, or credentials."""
        raw_text = decision_json_path.read_text(encoding="utf-8")
        forbidden_patterns = [
            "C:\\",
            "/home/",
            "/Users/",
            "password",
            "bearer ",
            "ghp_",
            "github_pat",
            "secret",
        ]
        for pattern in forbidden_patterns:
            assert pattern.lower() not in raw_text.lower()


class TestPrivacyAndRegressionGuards:
    """Regression tests preventing real identifier exposure in research artifacts."""

    def test_no_standalone_11_digit_numbers_in_research_doc(
        self, research_doc_path: Path
    ) -> None:
        """Ensure no concrete standalone 11-digit numbers are committed in markdown."""
        content = research_doc_path.read_text(encoding="utf-8")
        # Match standalone 11-digit numbers
        matches = re.findall(
            r"(?<![0-9A-Za-z/_\-])[0-9]{11}(?![0-9A-Za-z/_\-])", content
        )
        assert not matches, (
            f"Found concrete 11-digit numbers in research doc: {matches}"
        )

    def test_no_standalone_11_digit_numbers_in_decision_json(
        self, decision_json_path: Path
    ) -> None:
        """Ensure no concrete standalone 11-digit numbers exist in decision JSON."""
        content = decision_json_path.read_text(encoding="utf-8")
        matches = re.findall(r"(?<![0-9])[0-9]{11}(?![0-9])", content)
        assert not matches, (
            f"Found concrete 11-digit numbers in decision json: {matches}"
        )

    def test_evidence_source_table_reconciliation(
        self, research_doc_path: Path, decision_data: dict[str, Any]
    ) -> None:
        """Ensure source table entries reconcile with decision JSON counts."""
        doc_text = research_doc_path.read_text(encoding="utf-8")

        # Find all source rows like `SRC-PRI-01`, `SRC-SEC-01`, `SRC-COM-01`
        pri_sources = re.findall(r"`SRC-PRI-\d+`", doc_text)
        sec_sources = re.findall(r"`SRC-SEC-\d+`", doc_text)
        com_sources = re.findall(r"`SRC-COM-\d+`", doc_text)

        unique_pri = set(pri_sources)
        unique_sec = set(sec_sources)
        unique_com = set(com_sources)

        assert len(unique_pri) == 4, (
            f"Expected 4 primary sources, got {len(unique_pri)}"
        )
        assert len(unique_sec) == 7, (
            f"Expected 7 secondary sources, got {len(unique_sec)}"
        )
        assert len(unique_com) == 5, (
            f"Expected 5 community sources, got {len(unique_com)}"
        )

        # Verify max candidate counts do not exceed total available sources
        for candidate in decision_data["candidates"]:
            counts = candidate["evidence_counts"]
            assert counts["primary"] <= len(unique_pri)
            assert counts["secondary_technical"] <= len(unique_sec)
            assert counts["community"] <= len(unique_com)


class TestChecksumReferenceAlgorithms:
    """Verify research-only checksum algorithm variants and properties."""

    def test_checksum_bounds_variant_a(self) -> None:
        """Variant A computed check digit must always be in range 0..9."""
        for i in range(100):
            prefix = f"{i:010d}"
            check_digit = compute_legal_entity_checksum_variant_a(prefix)
            assert 0 <= check_digit <= 9

    def test_ascii_strict_input_enforcement(self) -> None:
        """Research reference functions strictly require ASCII numeric digits."""
        # Non-ASCII Persian digits must be rejected with ValueError
        persian_10 = "۱۲۳۴۵۶۷۸۹۰"
        arabic_10 = "١٢٣٤٥٦٧٨٩٠"
        with pytest.raises(ValueError, match="exactly 10 ASCII digits"):
            compute_legal_entity_checksum_variant_a(persian_10)
        with pytest.raises(ValueError, match="exactly 10 ASCII digits"):
            compute_legal_entity_checksum_variant_a(arabic_10)

        # Verification function returns False on non-ASCII digits
        persian_11 = "۱۲۳۴۵۶۷۸۹۰۱"
        arabic_11 = "١٢٣٤٥٦٧٨٩٠١"
        assert not verify_legal_entity_id_variant_a(persian_11)
        assert not verify_legal_entity_id_variant_a(arabic_11)

    def test_invalid_input_length_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly 10 ASCII digits"):
            compute_legal_entity_checksum_variant_a("123")
        with pytest.raises(ValueError, match="exactly 10 ASCII digits"):
            compute_legal_entity_checksum_variant_a("12345678901")
        with pytest.raises(ValueError, match="exactly 10 ASCII digits"):
            compute_legal_entity_checksum_variant_a("12345abcde")

    def test_repeated_digits_rejected(self) -> None:
        """All-identical digit strings must be rejected."""
        for d in range(10):
            repeated = str(d) * 11
            assert not verify_legal_entity_id_variant_a(repeated)
            assert not verify_legal_entity_id_variant_b(repeated)
            assert not verify_legal_entity_id_variant_c(repeated)
            assert not verify_legal_entity_id_variant_d(repeated)

    def test_wrong_length_rejected(self) -> None:
        assert not verify_legal_entity_id_variant_a("1234567890")
        assert not verify_legal_entity_id_variant_a("123456789012")
        assert not verify_legal_entity_id_variant_a("")

    def test_non_digit_rejected(self) -> None:
        assert not verify_legal_entity_id_variant_a("1010038714A")
        assert not verify_legal_entity_id_variant_a("10100 87143")

    def test_variant_disagreement_on_synthetic_prefixes(self) -> None:
        """Empirically prove that variants compute different checksums."""
        prefixes = [f"{n * 11111:010d}" for n in range(1, 10)]
        comparison = compare_checksum_variants(prefixes)
        assert len(comparison) == 9

        # Verify that variants do not all collapse into identical outputs
        variant_a_results = [v["variant_a"] for v in comparison.values()]
        variant_b_results = [v["variant_b"] for v in comparison.values()]
        assert variant_a_results != variant_b_results


class TestProjectInvariants:
    """Verify that Phase 27 maintained all zero-change production constraints."""

    def test_no_production_validators_added(self) -> None:
        assert not hasattr(fa_redact, "is_valid_iranian_legal_entity_id")
        assert not hasattr(fa_redact, "is_valid_postal_code")
        assert not hasattr(fa_redact, "is_valid_registration_number")

    def test_no_production_detectors_added(self) -> None:
        assert not hasattr(fa_redact, "IranianLegalEntityIDDetector")
        assert not hasattr(fa_redact, "IranianPostalCodeDetector")
        assert not hasattr(fa_redact, "IranianRegistrationNumberDetector")

    def test_default_detectors_unchanged(self) -> None:
        expected_default_types = (
            IranianNationalIDDetector,
            IranianMobileNumberDetector,
            IranianIBANDetector,
        )
        assert tuple(type(d) for d in _DEFAULT_DETECTORS) == expected_default_types

    def test_package_version_remains_0_3_0(self) -> None:
        assert fa_redact.__version__ == "0.3.0"

    def test_pyproject_dependencies_empty(self) -> None:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        assert "dependencies = []" in content
        assert 'version = "0.3.0"' in content
