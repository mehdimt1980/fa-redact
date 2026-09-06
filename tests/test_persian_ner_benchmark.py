"""Unit tests for Persian NER empirical benchmark utilities.

Tests exact token-to-span reconstruction, subword-to-span offset mapping,
strict BIO tag parsing, strict CoNLL parsing, tokenizer offset/alignment auditing,
recursive privacy key gating, and safe value-free result serialization without
requiring model weights or downloads.
"""

from __future__ import annotations

import json

import pytest
from research.evaluation import EntitySpan
from research.persian_ner_benchmark import (
    BenchmarkAggregateSummary,
    audit_tokenizer_alignment,
    bio_tokens_to_spans,
    bio_tokens_to_spans_with_stats,
    parse_bio_label,
    parse_conll_data,
    serialize_benchmark_result,
    subwords_to_entity_spans,
)


class TestParseBioLabel:
    """Test parse_bio_label with various tag formats and strict/lenient modes."""

    def test_standard_tags_with_underscore(self) -> None:
        assert parse_bio_label("B_PER") == ("B", "PERSON")
        assert parse_bio_label("I_PER") == ("I", "PERSON")
        assert parse_bio_label("B_ORG") == ("B", "ORG")
        assert parse_bio_label("I_LOC") == ("I", "LOC")
        assert parse_bio_label("O") == ("O", None)

    def test_standard_tags_with_hyphen(self) -> None:
        assert parse_bio_label("B-PER") == ("B", "PERSON")
        assert parse_bio_label("I-PER") == ("I", "PERSON")
        assert parse_bio_label("B-PERS") == ("B", "PERSON")
        assert parse_bio_label("I-Person") == ("I", "PERSON")
        assert parse_bio_label("B-person") == ("B", "PERSON")

    def test_empty_or_whitespace_label(self) -> None:
        assert parse_bio_label("") == ("O", None)
        assert parse_bio_label("   ") == ("O", None)

    def test_strict_mode_rejects_empty_label(self) -> None:
        with pytest.raises(ValueError, match="Empty or whitespace BIO label"):
            parse_bio_label("", strict=True)

    def test_strict_mode_rejects_invalid_prefix(self) -> None:
        with pytest.raises(ValueError, match="Invalid BIO prefix"):
            parse_bio_label("X_PER", strict=True)

    def test_strict_mode_rejects_missing_entity_type(self) -> None:
        with pytest.raises(ValueError, match="Missing entity type"):
            parse_bio_label("B_", strict=True)


class TestBioTokensToSpans:
    """Test reconstruction of text and gold spans from token sequences."""

    def test_exact_single_token_person(self) -> None:
        tokens = ["نامه", "از", "سهراب", "رسید"]
        tags = ["O", "O", "B_PER", "O"]
        text, spans = bio_tokens_to_spans(tokens, tags)

        assert text == "نامه از سهراب رسید"
        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=8, end=13, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "سهراب"

    def test_multi_token_person(self) -> None:
        tokens = ["دکتر", "محمد", "علی", "رجایی", "سخنرانی", "کرد"]
        tags = ["O", "B_PER", "I_PER", "I_PER", "O", "O"]
        text, spans = bio_tokens_to_spans(tokens, tags)

        assert text == "دکتر محمد علی رجایی سخنرانی کرد"
        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=5, end=19, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "محمد علی رجایی"

    def test_two_consecutive_person_entities(self) -> None:
        tokens = ["دیدار", "علی", "محمد", "برگزار", "شد"]
        tags = ["O", "B_PER", "B_PER", "O", "O"]
        text, spans = bio_tokens_to_spans(tokens, tags)

        assert text == "دیدار علی محمد برگزار شد"
        assert len(spans) == 2
        assert spans[0] == EntitySpan(start=6, end=9, type="PERSON")
        assert spans[1] == EntitySpan(start=10, end=14, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "علی"
        assert text[spans[1].start : spans[1].end] == "محمد"

    def test_leading_i_per_recovery(self) -> None:
        tokens = ["ملاقات", "رضایی", "با", "مدیر"]
        tags = ["O", "I_PER", "O", "O"]
        text, spans, recoveries = bio_tokens_to_spans_with_stats(tokens, tags)

        assert len(spans) == 1
        assert recoveries == 1
        assert spans[0] == EntitySpan(start=7, end=12, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "رضایی"

    def test_zwnj_in_token_span(self) -> None:
        tokens = ["آقای", "علی‌رضا", "حسینی", "آمد"]
        tags = ["O", "B_PER", "I_PER", "O"]
        text, spans = bio_tokens_to_spans(tokens, tags)

        assert "\u200c" in text
        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=5, end=18, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "علی‌رضا حسینی"

    def test_arabic_persian_character_variants(self) -> None:
        tokens = ["على", "كريمى", "پزشك", "است"]
        tags = ["B_PER", "I_PER", "O", "O"]
        text, spans = bio_tokens_to_spans(tokens, tags)

        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=0, end=9, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "على كريمى"

    def test_empty_tokens(self) -> None:
        text, spans = bio_tokens_to_spans([], [])
        assert text == ""
        assert spans == []

    def test_mismatched_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Tokens and tags length mismatch"):
            bio_tokens_to_spans(["علی"], ["B_PER", "I_PER"])


class TestSubwordsToEntitySpans:
    """Test mapping of fast tokenizer offsets and subword predictions to spans."""

    def test_subword_merging_and_offsets(self) -> None:
        text = "آقای طباطبایی نژاد آمد"
        offsets = [(0, 0), (0, 4), (5, 9), (9, 13), (14, 18), (19, 22), (0, 0)]
        labels = ["O", "O", "B_PER", "I_PER", "I_PER", "O", "O"]

        spans, failures = subwords_to_entity_spans(text, offsets, labels)
        assert failures == 0
        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=5, end=18, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "طباطبایی نژاد"

    def test_punctuation_adjacent_name(self) -> None:
        text = 'گزارش: "علی رضایی"، پزشک کشیک.'
        offsets = [
            (0, 0),
            (0, 6),
            (7, 8),
            (8, 11),
            (12, 17),
            (17, 18),
            (18, 19),
            (20, 24),
            (0, 0),
        ]
        labels = ["O", "O", "O", "B_PER", "I_PER", "O", "O", "O", "O"]

        spans, failures = subwords_to_entity_spans(text, offsets, labels)
        assert failures == 0
        assert len(spans) == 1
        assert spans[0] == EntitySpan(start=8, end=17, type="PERSON")
        assert text[spans[0].start : spans[0].end] == "علی رضایی"

    def test_empty_predictions(self) -> None:
        text = "متن بدون نام خاص"
        offsets = [(0, 0), (0, 3), (4, 8), (9, 12), (13, 16), (0, 0)]
        labels = ["O", "O", "O", "O", "O", "O"]

        spans, failures = subwords_to_entity_spans(text, offsets, labels)
        assert failures == 0
        assert spans == []


class TestTokenizerAlignmentAudit:
    """Test fast tokenizer character offset auditing."""

    def test_valid_monotonic_offsets(self) -> None:
        text = "علی رضایی آمد"
        offsets = [(0, 0), (0, 3), (4, 9), (10, 13), (0, 0)]
        failures = audit_tokenizer_alignment(text, offsets)
        assert failures == 0

    def test_out_of_bounds_offsets(self) -> None:
        text = "علی"
        offsets = [(0, 0), (0, 5), (0, 0)]
        failures = audit_tokenizer_alignment(text, offsets)
        assert failures >= 1

    def test_non_monotonic_offsets(self) -> None:
        text = "علی رضایی"
        offsets = [(0, 0), (4, 9), (0, 3), (0, 0)]
        failures = audit_tokenizer_alignment(text, offsets)
        assert failures >= 1


class TestParseConllData:
    """Test CoNLL dataset text parser with strict and pipe-token support."""

    def test_parse_conll_pipes_and_sentences(self) -> None:
        data = "علی|B_PER\nرضایی|I_PER\nآمد|O\n\nامروز|B_DAT\nهوا|O\nخوب|O\nاست|O\n"
        sentences = parse_conll_data(data)

        assert len(sentences) == 2
        assert sentences[0][0] == ["علی", "رضایی", "آمد"]
        assert sentences[0][1] == ["B_PER", "I_PER", "O"]
        assert sentences[1][0] == ["امروز", "هوا", "خوب", "است"]
        assert sentences[1][1] == ["B_DAT", "O", "O", "O"]

    def test_parse_pipe_character_as_token(self) -> None:
        data = "بخش|O\n||O\nاول|O\n"
        sentences = parse_conll_data(data, strict=True)
        assert len(sentences) == 1
        assert sentences[0][0] == ["بخش", "|", "اول"]
        assert sentences[0][1] == ["O", "O", "O"]

    def test_parse_strict_malformed_line_raises(self) -> None:
        data = "علی|B_PER\nتنها_بدون_تگ\n"
        with pytest.raises(ValueError, match="Malformed CoNLL line"):
            parse_conll_data(data, strict=True)


class TestBenchmarkSerializationAndPrivacy:
    """Test safe serialization and recursive privacy key gating."""

    def test_deterministic_serialization(self) -> None:
        summary = BenchmarkAggregateSummary(
            schema_version="1.1.0",
            benchmark_protocol="PERSON-only entity-level exact-span",
            model_id="HooshvareLab/bert-fa-base-uncased-ner-peyma",
            model_revision="8b7b63371aa8f1fdad62c0f82d462a22b91b37ab",
            model_license="Apache-2.0",
            dataset_source="ParsiAI/PEYMA",
            dataset_source_kind="community_mirror",
            dataset_revision="c9995786945706010f000d4196b0a9ecbd6b96c5",
            dataset_split="test",
            dataset_file_sha256="59a5f7f2bc2f6d89965a8b832a371293df23976eb7552a41916976d3a7dd7c96",
            original_dataset="PEYMA",
            original_dataset_terms="free for research purposes (authors)",
            mirror_declared_license="Apache-2.0",
            mirror_relicensing_authority="not_verified",
            package_redistribution_status="requires_verification",
            evaluated_sentences=1026,
            gold_person_entities=434,
            predicted_person_entities=433,
            true_positives=430,
            false_positives=3,
            false_negatives=4,
            precision=0.993072,
            recall=0.990783,
            f1=0.991926,
            boundary_errors=3,
            pure_false_positives=0,
            pure_false_negatives=1,
            duplicate_predictions=0,
            leading_i_recoveries=0,
            basic_offset_validation_failures=0,
            tokenizer_alignment_failures=0,
            truncated_sentences=0,
            max_tokenized_length=153,
            sentences_with_zwnj=0,
            gold_person_with_zwnj=0,
            sentences_with_arabic_variants=0,
            gold_person_with_arabic_variants=0,
            python_version="3.10.11",
            torch_version="2.7.0+cpu",
            transformers_version="4.49.0",
            tokenizers_version="0.21.1",
            platform="Windows-10",
            evaluation_policy="exact_span_entity_level",
        )

        serialized = serialize_benchmark_result(summary)
        parsed = json.loads(serialized)

        assert parsed["model_id"] == "HooshvareLab/bert-fa-base-uncased-ner-peyma"
        assert parsed["true_positives"] == 430
        assert parsed["false_positives"] == 3
        assert parsed["false_negatives"] == 4
        assert parsed["f1"] == 0.991926
        assert parsed["boundary_errors"] == 3
        assert (
            parsed["dataset_file_sha256"]
            == "59a5f7f2bc2f6d89965a8b832a371293df23976eb7552a41916976d3a7dd7c96"
        )

    def test_top_level_forbidden_sensitive_key_rejection(self) -> None:
        bad_summary = {
            "model_id": "test-model",
            "true_positives": 10,
            "text": "Sensitive patient note with names",
        }
        with pytest.raises(ValueError, match="Forbidden sensitive key 'text'"):
            serialize_benchmark_result(bad_summary)

    def test_nested_forbidden_sensitive_key_rejection(self) -> None:
        bad_nested = {
            "model_id": "test-model",
            "metadata": {
                "patient_info": {
                    "names": ["احمد رضایی"],
                }
            },
        }
        with pytest.raises(ValueError, match="Forbidden sensitive key 'names'"):
            serialize_benchmark_result(bad_nested)

    def test_list_nested_forbidden_sensitive_key_rejection(self) -> None:
        bad_in_list = {
            "model_id": "test-model",
            "diagnostics": [
                {"category": "ok"},
                {"tokens": ["علی", "آمد"]},
            ],
        }
        with pytest.raises(ValueError, match="Forbidden sensitive key 'tokens'"):
            serialize_benchmark_result(bad_in_list)

    def test_no_source_text_in_serialized_json(self) -> None:
        summary = BenchmarkAggregateSummary(
            schema_version="1.1.0",
            benchmark_protocol="PERSON-only entity-level exact-span",
            model_id="HooshvareLab/bert-fa-base-uncased-ner-peyma",
            model_revision="8b7b63371aa8f1fdad62c0f82d462a22b91b37ab",
            model_license="Apache-2.0",
            dataset_source="ParsiAI/PEYMA",
            dataset_source_kind="community_mirror",
            dataset_revision="c9995786945706010f000d4196b0a9ecbd6b96c5",
            dataset_split="test",
            dataset_file_sha256="59a5f7f2bc2f6d89965a8b832a371293df23976eb7552a41916976d3a7dd7c96",
            original_dataset="PEYMA",
            original_dataset_terms="free for research purposes (authors)",
            mirror_declared_license="Apache-2.0",
            mirror_relicensing_authority="not_verified",
            package_redistribution_status="requires_verification",
            evaluated_sentences=100,
            gold_person_entities=50,
            predicted_person_entities=50,
            true_positives=50,
            false_positives=0,
            false_negatives=0,
            precision=1.0,
            recall=1.0,
            f1=1.0,
            boundary_errors=0,
            pure_false_positives=0,
            pure_false_negatives=0,
            duplicate_predictions=0,
            leading_i_recoveries=0,
            basic_offset_validation_failures=0,
            tokenizer_alignment_failures=0,
            truncated_sentences=0,
            max_tokenized_length=50,
            sentences_with_zwnj=0,
            gold_person_with_zwnj=0,
            sentences_with_arabic_variants=0,
            gold_person_with_arabic_variants=0,
            python_version="3.10.11",
            torch_version="2.7.0+cpu",
            transformers_version="4.49.0",
            tokenizers_version="0.21.1",
            platform="Windows-10",
            evaluation_policy="exact_span_entity_level",
        )
        serialized = serialize_benchmark_result(summary)
        for forbidden in (
            "text",
            "tokens",
            "names",
            "entities",
            "snippets",
            "raw_predictions",
        ):
            assert f'"{forbidden}"' not in serialized
