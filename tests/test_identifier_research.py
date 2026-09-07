"""Tests for Phase 27 identifier research, decision artifacts, and reference algorithms.

Ensures research artifacts conform strictly to schemas, invariants, determinism,
isolation rules, and that no production code or dependencies were altered.
"""

from __future__ import annotations

import json
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
def decision_json_path() -> Path:
    return (
        Path(__file__).parent.parent
        / "research"
        / "results"
        / "phase27_identifier_decision.json"
    )


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


class TestChecksumReferenceAlgorithms:
    """Verify research-only checksum algorithm variants and properties."""

    def test_checksum_bounds_variant_a(self) -> None:
        """Variant A computed check digit must always be in range 0..9."""
        for i in range(100):
            prefix = f"{i:010d}"
            check_digit = compute_legal_entity_checksum_variant_a(prefix)
            assert 0 <= check_digit <= 9

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
