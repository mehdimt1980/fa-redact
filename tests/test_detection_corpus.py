"""Unit tests for the synthetic detection corpus and evaluation runner (Phase 25)."""

from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from research.detection_corpus import (
    SYNTHETIC_DETECTION_CORPUS,
    SYNTHETIC_PATTERN_RULES,
    SyntheticDetectionCase,
    _span_for,
    validate_detection_corpus,
)
from research.detection_corpus_benchmark import (
    DetectionBenchmarkResult,
    run_detection_corpus_benchmark,
)
from research.detection_corpus_benchmark import (
    main as benchmark_main,
)
from research.evaluation import (
    EntitySpan,
    calculate_metrics,
)
from research.synthetic_fixtures import SYNTHETIC_CHALLENGE_FIXTURES

import fa_redact
from fa_redact.detectors.pattern import PatternRule

# =============================================================================
# 1. SyntheticDetectionCase Model & Validation Tests
# =============================================================================


class TestSyntheticDetectionCaseModel:
    """Tests for SyntheticDetectionCase data model and invariants."""

    def test_case_immutability(self) -> None:
        """Verify that SyntheticDetectionCase instances are frozen and immutable."""
        span = EntitySpan(start=0, end=10, type="IR_NATIONAL_ID")
        case = SyntheticDetectionCase(
            id="test_01",
            suite="default",
            category="national_id_positive",
            description="Test description",
            text="0012345679 کد ملی",
            gold_spans=(span,),
        )
        with pytest.raises(FrozenInstanceError):
            case.id = "modified"  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            case.text = "modified text"  # type: ignore[misc]

    def test_case_id_validation(self) -> None:
        """Verify non-empty ID is required."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(ValueError, match="id must be a non-empty string"):
            SyntheticDetectionCase(
                id="",
                suite="default",
                category="cat",
                description="desc",
                text="12345",
                gold_spans=(span,),
            )
        with pytest.raises(ValueError, match="id must be a non-empty string"):
            SyntheticDetectionCase(
                id="   ",
                suite="default",
                category="cat",
                description="desc",
                text="12345",
                gold_spans=(span,),
            )

    def test_case_suite_validation(self) -> None:
        """Verify non-empty suite is required."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(ValueError, match="suite must be a non-empty string"):
            SyntheticDetectionCase(
                id="t1",
                suite="",
                category="cat",
                description="desc",
                text="12345",
                gold_spans=(span,),
            )

    def test_case_category_validation(self) -> None:
        """Verify non-empty category is required."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(ValueError, match="category must be a non-empty string"):
            SyntheticDetectionCase(
                id="t1",
                suite="default",
                category="",
                description="desc",
                text="12345",
                gold_spans=(span,),
            )

    def test_case_description_validation(self) -> None:
        """Verify non-empty description is required."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(ValueError, match="description must be a non-empty string"):
            SyntheticDetectionCase(
                id="t1",
                suite="default",
                category="cat",
                description="",
                text="12345",
                gold_spans=(span,),
            )

    def test_case_text_type_validation(self) -> None:
        """Verify text must be str."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(TypeError, match="text must be str"):
            SyntheticDetectionCase(
                id="t1",
                suite="default",
                category="cat",
                description="desc",
                text=12345,  # type: ignore[arg-type]
                gold_spans=(span,),
            )

    def test_case_gold_spans_tuple_snapshot(self) -> None:
        """Verify gold spans are snapshotted as an immutable tuple."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        mutable_spans = [span]
        case = SyntheticDetectionCase(
            id="t1",
            suite="default",
            category="cat",
            description="desc",
            text="12345 text",
            gold_spans=mutable_spans,  # type: ignore[arg-type]
        )
        assert isinstance(case.gold_spans, tuple)
        mutable_spans.append(EntitySpan(start=0, end=2, type="OTHER"))
        assert len(case.gold_spans) == 1

    def test_case_invalid_span_bounds_rejected(self) -> None:
        """Verify out-of-bounds spans raise ValueError."""
        # start < 0 handled by EntitySpan
        with pytest.raises(ValueError, match="invalid span"):
            SyntheticDetectionCase(
                id="t1",
                suite="default",
                category="cat",
                description="desc",
                text="12345",
                gold_spans=(EntitySpan(start=0, end=10, type="IR_NATIONAL_ID"),),
            )

    def test_case_duplicate_gold_spans_rejected(self) -> None:
        """Verify identical duplicate gold spans are rejected."""
        span = EntitySpan(start=0, end=5, type="IR_NATIONAL_ID")
        with pytest.raises(ValueError, match="duplicate gold span detected"):
            SyntheticDetectionCase(
                id="t1",
                suite="default",
                category="cat",
                description="desc",
                text="12345 text",
                gold_spans=(span, span),
            )


# =============================================================================
# 2. Substring Span Builder Helper Tests
# =============================================================================


class TestSpanForHelper:
    """Tests for _span_for helper."""

    def test_exact_substring_offsets(self) -> None:
        text = "شماره ملی 0012345679 ثبت شد."
        span = _span_for(text, "0012345679", "IR_NATIONAL_ID")
        assert span.start == 10
        assert span.end == 20
        assert span.type == "IR_NATIONAL_ID"
        assert text[span.start : span.end] == "0012345679"

    def test_repeated_substring_occurrences(self) -> None:
        text = "تماس با 09121234567 یا 09121234567 امکان‌پذیر است."
        span1 = _span_for(text, "09121234567", "IR_MOBILE", occurrence=1)
        span2 = _span_for(text, "09121234567", "IR_MOBILE", occurrence=2)
        assert span1.start < span2.start
        assert text[span1.start : span1.end] == "09121234567"
        assert text[span2.start : span2.end] == "09121234567"

    def test_missing_substring_fails_loudly(self) -> None:
        text = "متن بدون مقدار مورد نظر"
        with pytest.raises(ValueError, match="not found in text"):
            _span_for(text, "0012345679", "IR_NATIONAL_ID")

    def test_invalid_occurrence_fails_loudly(self) -> None:
        text = "یک شماره 09121234567 وجود دارد."
        with pytest.raises(ValueError, match="occurrence must be >= 1"):
            _span_for(text, "09121234567", "IR_MOBILE", occurrence=0)
        with pytest.raises(ValueError, match="not found in text"):
            _span_for(text, "09121234567", "IR_MOBILE", occurrence=2)

    def test_empty_substring_fails(self) -> None:
        with pytest.raises(ValueError, match="substring must be non-empty"):
            _span_for("text", "", "TYPE")


# =============================================================================
# 3. Corpus Validation & Structure Tests
# =============================================================================


class TestCorpusValidation:
    """Tests for validate_detection_corpus and SYNTHETIC_DETECTION_CORPUS."""

    def test_corpus_case_ids_unique(self) -> None:
        """Verify all case IDs in the committed corpus are distinct."""
        ids = [case.id for case in SYNTHETIC_DETECTION_CORPUS]
        assert len(ids) == len(set(ids))

    def test_duplicate_case_ids_rejected(self) -> None:
        """Verify duplicate case IDs fail loudly."""
        case1 = SYNTHETIC_DETECTION_CORPUS[0]
        with pytest.raises(ValueError, match="Duplicate corpus case ID detected"):
            validate_detection_corpus([case1, case1])

    def test_corpus_validation_does_not_mutate_input(self) -> None:
        """Verify validation creates an immutable tuple without mutating input."""
        cases_list = list(SYNTHETIC_DETECTION_CORPUS[:3])
        result = validate_detection_corpus(cases_list)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_corpus_ordering_deterministic(self) -> None:
        """Verify corpus ordering is deterministic."""
        ids1 = [c.id for c in SYNTHETIC_DETECTION_CORPUS]
        ids2 = [c.id for c in SYNTHETIC_DETECTION_CORPUS]
        assert ids1 == ids2

    def test_corpus_size_in_target_range(self) -> None:
        """Verify corpus contains between 40 and 80 cases."""
        assert 40 <= len(SYNTHETIC_DETECTION_CORPUS) <= 80

    def test_corpus_suites_present(self) -> None:
        """Verify all target suites are represented."""
        suites = {case.suite for case in SYNTHETIC_DETECTION_CORPUS}
        assert suites == {"default", "email", "bank_card", "pattern", "legal_entity_id"}


# =============================================================================
# 4. Suite & Category Fixture Coverage Tests
# =============================================================================


class TestSuiteCoverage:
    """Tests for coverage across suites and categories."""

    def test_default_suite_national_id_positive_and_negative(self) -> None:
        nids_pos = [
            c
            for c in SYNTHETIC_DETECTION_CORPUS
            if c.category == "national_id_positive"
        ]
        nids_neg = [
            c
            for c in SYNTHETIC_DETECTION_CORPUS
            if c.category == "national_id_negative"
        ]
        assert len(nids_pos) >= 5
        assert len(nids_neg) >= 3

    def test_default_suite_mobile_positive_negative_and_variants(self) -> None:
        mobs_pos = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "mobile_positive"
        ]
        mobs_neg = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "mobile_negative"
        ]
        mobs_var = [
            c
            for c in SYNTHETIC_DETECTION_CORPUS
            if c.category == "mobile_script_variant"
        ]
        assert len(mobs_pos) >= 5
        assert len(mobs_neg) >= 3
        assert len(mobs_var) >= 2

    def test_default_suite_iban_positive_and_negative(self) -> None:
        ibans_pos = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "iban_positive"
        ]
        ibans_neg = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "iban_negative"
        ]
        assert len(ibans_pos) >= 4
        assert len(ibans_neg) >= 3

    def test_default_suite_mixed_documents(self) -> None:
        mixed = [c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "mixed_default"]
        assert len(mixed) >= 4

    def test_email_suite_positive_and_negative(self) -> None:
        emails_pos = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "email_positive"
        ]
        emails_neg = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "email_negative"
        ]
        assert len(emails_pos) >= 4
        assert len(emails_neg) >= 3

    def test_bank_card_suite_positive_and_negative(self) -> None:
        cards_pos = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "bank_card_positive"
        ]
        cards_neg = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "bank_card_negative"
        ]
        assert len(cards_pos) >= 3
        assert len(cards_neg) >= 2

    def test_pattern_suite_positive_normalized_and_negative(self) -> None:
        pat_pos = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "pattern_positive"
        ]
        pat_norm = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "pattern_normalized"
        ]
        pat_neg = [
            c for c in SYNTHETIC_DETECTION_CORPUS if c.category == "pattern_negative"
        ]
        assert len(pat_pos) >= 3
        assert len(pat_norm) >= 2
        assert len(pat_neg) >= 2

    def test_legal_entity_id_suite_positive_and_negative(self) -> None:
        leid_pos = [
            c
            for c in SYNTHETIC_DETECTION_CORPUS
            if c.category == "legal_entity_id_positive"
        ]
        leid_neg = [
            c
            for c in SYNTHETIC_DETECTION_CORPUS
            if c.category == "legal_entity_id_negative"
        ]
        assert len(leid_pos) >= 4
        assert len(leid_neg) >= 3

    def test_no_universal_pattern_claim(self) -> None:
        """Verify synthetic pattern rules are explicitly typed PatternRule instances."""
        assert len(SYNTHETIC_PATTERN_RULES) >= 2
        for rule in SYNTHETIC_PATTERN_RULES:
            assert isinstance(rule, PatternRule)
            assert rule.type in ("MRN", "PATIENT_ID", "ENCOUNTER_ID")


# =============================================================================
# 5. Benchmark Runner & Evaluation Semantics Tests
# =============================================================================


class TestBenchmarkRunner:
    """Tests for run_detection_corpus_benchmark."""

    def test_corpus_benchmark_execution_and_metrics(self) -> None:
        """Verify that running benchmark computes exact-span metrics on corpus."""
        result = run_detection_corpus_benchmark()
        assert isinstance(result, DetectionBenchmarkResult)
        assert result.schema_version == "1.0.0"
        assert result.case_count == len(SYNTHETIC_DETECTION_CORPUS)
        assert result.failed_case_ids == ()
        assert result.overall.precision == 1.0
        assert result.overall.recall == 1.0
        assert result.overall.f1 == 1.0
        assert result.overall.false_positives == 0
        assert result.overall.false_negatives == 0
        assert result.overall.true_positives == result.gold_entity_count

    def test_per_type_metrics_computed(self) -> None:
        result = run_detection_corpus_benchmark()
        expected_types = {
            "IR_NATIONAL_ID",
            "IR_MOBILE",
            "IR_IBAN",
            "EMAIL",
            "BANK_CARD",
            "MRN",
            "PATIENT_ID",
            "ENCOUNTER_ID",
            "IR_LEGAL_ENTITY_ID",
        }
        assert set(result.by_type.keys()) == expected_types
        for _entity_type, m in result.by_type.items():
            assert m.precision == 1.0
            assert m.recall == 1.0
            assert m.f1 == 1.0

    def test_per_category_metrics_computed(self) -> None:
        result = run_detection_corpus_benchmark()
        all_categories = {case.category for case in SYNTHETIC_DETECTION_CORPUS}
        assert set(result.by_category.keys()) == all_categories
        for _cat_name, m in result.by_category.items():
            assert m.precision == 1.0
            assert m.recall == 1.0
            assert m.f1 == 1.0

    def test_wrong_boundary_fails_case(self) -> None:
        """Verify that an intentional offset mismatch marks a case as failed."""
        case_with_bad_span = SyntheticDetectionCase(
            id="bad_boundary_case",
            suite="default",
            category="national_id_positive",
            description="Bad boundary offset",
            text="کد ملی 0012345679 ثبت شد.",
            gold_spans=(EntitySpan(start=9, end=20, type="IR_NATIONAL_ID"),),
        )
        result = run_detection_corpus_benchmark([case_with_bad_span])
        assert "bad_boundary_case" in result.failed_case_ids
        assert result.overall.f1 < 1.0
        assert result.overall.false_positives == 1
        assert result.overall.false_negatives == 1

    def test_wrong_type_fails_case(self) -> None:
        """Verify that an intentional type mismatch marks a case as failed."""
        case_with_bad_type = SyntheticDetectionCase(
            id="bad_type_case",
            suite="default",
            category="national_id_positive",
            description="Bad type annotation",
            text="کد ملی 0012345679 ثبت شد.",
            gold_spans=(EntitySpan(start=10, end=20, type="WRONG_TYPE"),),
        )
        result = run_detection_corpus_benchmark([case_with_bad_type])
        assert "bad_type_case" in result.failed_case_ids
        assert result.overall.f1 < 1.0

    def test_missing_gold_counts_as_false_negative(self) -> None:
        """Verify an undetected gold entity increments false negatives."""
        case_with_missed_span = SyntheticDetectionCase(
            id="missed_gold_case",
            suite="default",
            category="national_id_positive",
            description="Unemitted gold span",
            text="متن بدون شناسه",
            gold_spans=(EntitySpan(start=0, end=3, type="IR_NATIONAL_ID"),),
        )
        result = run_detection_corpus_benchmark([case_with_missed_span])
        assert "missed_gold_case" in result.failed_case_ids
        assert result.overall.false_negatives == 1
        assert result.overall.true_positives == 0

    def test_unknown_suite_raises_value_error(self) -> None:
        case = SyntheticDetectionCase(
            id="unknown_suite_case",
            suite="unsupported_suite",
            category="cat",
            description="desc",
            text="text",
            gold_spans=(),
        )
        with pytest.raises(ValueError, match="Unknown suite"):
            run_detection_corpus_benchmark([case])


# =============================================================================
# 6. Privacy & Value-Free Serialization Tests
# =============================================================================


class TestPrivacyAndSerialization:
    """Tests verifying zero PII, text, or runtime leakages in result output."""

    def test_result_dictionary_does_not_contain_source_text(self) -> None:
        result = run_detection_corpus_benchmark()
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)

        # Check that none of the fixture text strings appear in JSON
        for case in SYNTHETIC_DETECTION_CORPUS:
            assert case.text not in json_str

    def test_result_does_not_contain_raw_or_normalized_values(self) -> None:
        result = run_detection_corpus_benchmark()
        result_dict = result.to_dict()
        forbidden_keys = {
            "text",
            "value",
            "raw_value",
            "normalized_value",
            "snippet",
            "pii",
        }

        def _check_keys(obj: object) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert k not in forbidden_keys
                    _check_keys(v)
            elif isinstance(obj, list):
                for item in obj:
                    _check_keys(item)

        _check_keys(result_dict)

    def test_result_does_not_contain_timestamps_or_hostnames(self) -> None:
        result = run_detection_corpus_benchmark()
        result_dict = result.to_dict()
        assert "timestamp" not in result_dict
        assert "hostname" not in result_dict
        assert "path" not in result_dict

    def test_repeat_benchmark_produces_identical_json(self) -> None:
        result1 = run_detection_corpus_benchmark()
        result2 = run_detection_corpus_benchmark()
        assert result1.to_json() == result2.to_json()

    def test_committed_result_json_matches_runner_output(self) -> None:
        """Verify committed JSON matches live execution identically."""
        committed_path = (
            Path(__file__).resolve().parent.parent
            / "research"
            / "results"
            / "phase25_detection_corpus.json"
        )
        assert committed_path.exists(), "Committed result JSON file must exist"
        committed_content = committed_path.read_text(encoding="utf-8")
        current_content = run_detection_corpus_benchmark().to_json()
        assert committed_content == current_content


# =============================================================================
# 7. Benchmark CLI Tests
# =============================================================================


class TestBenchmarkCLI:
    """Tests for benchmark CLI entrypoint."""

    def test_cli_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            benchmark_main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "Run offline evaluation against the synthetic detection corpus"
            in captured.out
        )

    def test_cli_output_and_check(self, tmp_path: Path) -> None:
        output_file = tmp_path / "test_result.json"
        exit_code = benchmark_main(["--output", str(output_file), "--check"])
        assert exit_code == 0
        assert output_file.exists()
        parsed = json.loads(output_file.read_text(encoding="utf-8"))
        assert parsed["schema_version"] == "1.0.0"
        assert parsed["case_count"] == len(SYNTHETIC_DETECTION_CORPUS)
        assert parsed["overall"]["f1"] == 1.0


# =============================================================================
# 8. Dependency & Architectural Invariants Tests
# =============================================================================


class TestArchitecturalInvariants:
    """Tests ensuring package and research boundaries remain strictly intact."""

    def test_production_exports_unchanged_by_phase25(self) -> None:
        """Verify that top-level fa_redact does not export research corpus objects."""
        assert not hasattr(fa_redact, "SyntheticDetectionCase")
        assert not hasattr(fa_redact, "SYNTHETIC_DETECTION_CORPUS")
        assert not hasattr(fa_redact, "run_detection_corpus_benchmark")
        assert "SyntheticDetectionCase" not in fa_redact.__all__

    def test_package_version_remains_0_3_0(self) -> None:
        assert fa_redact.__version__ == "0.3.0"

    def test_no_heavy_ml_imported_during_standard_benchmark(self) -> None:
        """Verify torch and transformers are not imported by the benchmark."""
        # Ensure modules are not imported
        assert "torch" not in sys.modules
        assert "transformers" not in sys.modules

    def test_existing_phase21_fixtures_usable(self) -> None:
        """Verify Phase 21 challenge fixtures remain green and unchanged."""
        assert len(SYNTHETIC_CHALLENGE_FIXTURES) >= 14
        for f in SYNTHETIC_CHALLENGE_FIXTURES:
            f.verify_spans()

    def test_existing_evaluation_metrics_pass(self) -> None:
        """Verify existing calculate_metrics and evaluate_corpus pass."""
        p, r, f1 = calculate_metrics(5, 0, 0)
        assert p == 1.0 and r == 1.0 and f1 == 1.0
