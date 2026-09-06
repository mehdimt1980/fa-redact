"""Persian Named Entity Recognition (NER) empirical benchmark runner.

This module provides deterministic, value-free utilities and an executable
runner for:
1. Parsing CoNLL-format dataset splits with strict formatting validation.
2. Reconstructing canonical evaluation text and gold character spans from
   token/BIO sequences.
3. Mapping fast tokenizer subword predictions and character offsets to exact
   reconstructed-text entity spans with monotonic offset and bounds auditing.
4. Evaluating PERSON exact-span precision, recall, and F1.
5. Performing deterministic, privacy-safe error categorization (boundary errors,
   pure false positives, pure false negatives).
6. Serializing value-free, privacy-safe benchmark aggregate results with
   recursive privacy key gating.
7. Executing offline, reproducible model benchmarks from local assets.

Zero runtime dependencies are required for the utility functions.
Model execution requires optional research dependencies (transformers, torch),
which are loaded lazily only during benchmark execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research.evaluation import EntitySpan, analyze_errors, evaluate_exact_spans

# Standard PERSON label identifiers
PERSON_LABEL_SET: frozenset[str] = frozenset(
    {"PER", "PERS", "PERSON", "Person", "person"}
)

FORBIDDEN_RESULT_KEYS: frozenset[str] = frozenset(
    {
        "text",
        "tokens",
        "names",
        "entities",
        "snippets",
        "raw_predictions",
        "values",
        "pii",
        "sentences",
        "raw_text",
        "gold_text",
        "pred_text",
    }
)


def parse_bio_label(label: str, *, strict: bool = False) -> tuple[str, str | None]:
    """Parse a BIO/IOB tag into prefix ('B', 'I', 'O') and entity type.

    Accepts delimiters '_' and '-' (e.g. 'B_PER', 'B-PER', 'I_PER', 'O').
    Maps person-related type labels (PER, PERS, Person, person) to 'PERSON'.

    Args:
        label: Raw label string.
        strict: If True, reject empty labels, invalid prefixes, or missing entity types.

    Returns:
        Tuple of (prefix, normalized_entity_type).
        If prefix is 'O', entity_type is None.

    Raises:
        ValueError: If strict is True and the label is malformed.
    """
    clean_label = label.strip()
    if not clean_label:
        if strict:
            raise ValueError("Empty or whitespace BIO label encountered")
        return ("O", None)

    if clean_label == "O":
        return ("O", None)

    # Handle B_PER, B-PER, I_PER, I-PER, etc.
    if "_" in clean_label:
        prefix, _, raw_type = clean_label.partition("_")
    elif "-" in clean_label:
        prefix, _, raw_type = clean_label.partition("-")
    else:
        prefix_candidate = clean_label[0].upper()
        if prefix_candidate in ("B", "I", "O"):
            prefix = prefix_candidate
            raw_type = clean_label[1:]
        else:
            if strict:
                raise ValueError(
                    f"Invalid BIO prefix in label '{label}'; expected B, I, or O prefix"
                )
            prefix = "B"
            raw_type = clean_label

    prefix = prefix.upper()
    if prefix not in ("B", "I", "O"):
        if strict:
            raise ValueError(f"Invalid BIO prefix '{prefix}' in label '{label}'")
        prefix = "B"

    raw_type_clean = raw_type.strip()
    if prefix == "O":
        return ("O", None)

    if not raw_type_clean:
        if strict:
            raise ValueError(f"Missing entity type in BIO label '{label}'")
        return ("O", None)

    # Normalize entity type
    if raw_type_clean in PERSON_LABEL_SET:
        norm_type = "PERSON"
    else:
        norm_type = raw_type_clean.upper()

    return (prefix, norm_type)


def bio_tokens_to_spans(
    tokens: Sequence[str],
    tags: Sequence[str],
    *,
    target_type: str = "PERSON",
) -> tuple[str, list[EntitySpan]]:
    """Reconstruct sentence text and exact gold entity spans from tokens and BIO tags.

    Tokens are joined with single spaces to form the deterministic evaluation text:
    `text = " ".join(tokens)`. Token character offsets are tracked directly in `text`.

    BIO entity boundaries are parsed as follows:
    - 'B-<TYPE>' starts a new entity.
    - 'I-<TYPE>' matching the active entity type continues the entity.
    - 'I-<TYPE>' without a preceding matching B (leading I) is recovered as starting
      a new entity.
    - Consecutive 'B-<TYPE>' tags are treated as distinct contiguous entities.
    - 'O' or type transitions close the active entity.

    Args:
        tokens: Sequence of token strings.
        tags: Sequence of BIO tag strings (e.g. 'B_PER', 'I_PER', 'O').
        target_type: Entity type to isolate (defaults to 'PERSON').

    Returns:
        Tuple of (reconstructed_text, entity_spans).

    Raises:
        ValueError: If len(tokens) != len(tags) or if extracted span slices are invalid.
    """
    text, spans, _ = bio_tokens_to_spans_with_stats(
        tokens, tags, target_type=target_type
    )
    return text, spans


def bio_tokens_to_spans_with_stats(
    tokens: Sequence[str],
    tags: Sequence[str],
    *,
    target_type: str = "PERSON",
) -> tuple[str, list[EntitySpan], int]:
    """Reconstruct text, exact gold spans, and count leading-I tag recoveries."""
    if len(tokens) != len(tags):
        raise ValueError(
            f"Tokens and tags length mismatch: {len(tokens)} != {len(tags)}"
        )

    if not tokens:
        return ("", [], 0)

    # Reconstruct text and compute token offsets
    token_offsets: list[tuple[int, int]] = []
    current_pos = 0
    text_parts: list[str] = []

    for i, tok in enumerate(tokens):
        if i > 0:
            current_pos += 1  # Space separator
        start = current_pos
        end = start + len(tok)
        token_offsets.append((start, end))
        current_pos = end
        text_parts.append(tok)

    reconstructed_text = " ".join(text_parts)

    spans: list[EntitySpan] = []
    active_start: int | None = None
    active_end: int | None = None
    leading_i_recoveries = 0

    for i, tag in enumerate(tags):
        prefix, entity_type = parse_bio_label(tag)
        tok_start, tok_end = token_offsets[i]

        if prefix == "B":
            if active_start is not None and active_end is not None:
                spans.append(
                    EntitySpan(start=active_start, end=active_end, type=target_type)
                )
                active_start = None
                active_end = None

            if entity_type == target_type:
                active_start = tok_start
                active_end = tok_end

        elif prefix == "I":
            if entity_type == target_type:
                if active_start is not None:
                    active_end = tok_end
                else:
                    # Leading I-tag recovery
                    leading_i_recoveries += 1
                    active_start = tok_start
                    active_end = tok_end
            else:
                if active_start is not None and active_end is not None:
                    spans.append(
                        EntitySpan(start=active_start, end=active_end, type=target_type)
                    )
                    active_start = None
                    active_end = None

        else:  # "O"
            if active_start is not None and active_end is not None:
                spans.append(
                    EntitySpan(start=active_start, end=active_end, type=target_type)
                )
                active_start = None
                active_end = None

    if active_start is not None and active_end is not None:
        spans.append(EntitySpan(start=active_start, end=active_end, type=target_type))

    # Verify all spans slice valid non-empty substrings
    for span in spans:
        slice_str = reconstructed_text[span.start : span.end]
        if not slice_str or slice_str.strip() == "":
            raise ValueError(
                f"Invalid empty slice for reconstructed span ({span.start}, {span.end})"
            )

    return (reconstructed_text, spans, leading_i_recoveries)


def audit_tokenizer_alignment(
    text: str,
    token_offsets: Sequence[tuple[int, int]],
) -> int:
    """Audit fast tokenizer character offsets for monotonicity and bounds fidelity.

    Verifies for all non-special tokens:
    1. 0 <= start <= end <= len(text)
    2. start >= previous_end (monotonic non-overlapping subwords)
    3. If start < end, text[start:end] is a valid non-empty slice.

    Args:
        text: Evaluated string.
        token_offsets: Fast tokenizer character offsets (start, end).

    Returns:
        Number of alignment violations detected.
    """
    alignment_failures = 0
    text_len = len(text)
    prev_end = 0

    for start, end in token_offsets:
        # Special tokens: (0, 0)
        if start == 0 and end == 0:
            continue

        if start < 0 or end > text_len or start > end:
            alignment_failures += 1
            continue

        if start < prev_end:
            alignment_failures += 1

        if start < end:
            slice_str = text[start:end]
            if len(slice_str) != (end - start):
                alignment_failures += 1

        prev_end = end

    return alignment_failures


def subwords_to_entity_spans(
    text: str,
    token_offsets: Sequence[tuple[int, int]],
    predicted_labels: Sequence[str],
    *,
    target_type: str = "PERSON",
) -> tuple[list[EntitySpan], int]:
    """Convert tokenizer subword offsets and predicted tags to exact spans.

    Maps subword predictions to original character offsets in `text`.
    Validates that every created span slices a valid non-empty substring in `text`.

    Args:
        text: Evaluated text string.
        token_offsets: List of (start, end) character offsets from fast tokenizer.
        predicted_labels: List of predicted tag strings for each subword token.
        target_type: Target entity type to extract (default 'PERSON').

    Returns:
        Tuple of (predicted_spans, basic_offset_validation_failures).
    """
    if len(token_offsets) != len(predicted_labels):
        raise ValueError(
            f"Offset and label length mismatch: {len(token_offsets)} "
            f"!= {len(predicted_labels)}"
        )

    spans: list[EntitySpan] = []
    basic_failures = 0

    active_start: int | None = None
    active_end: int | None = None

    for offset, label in zip(token_offsets, predicted_labels, strict=True):
        start, end = offset
        if start == end:  # Special token
            continue

        prefix, entity_type = parse_bio_label(label)

        if prefix == "B":
            if active_start is not None and active_end is not None:
                span, failure = _create_validated_span(
                    text, active_start, active_end, target_type
                )
                if span is not None:
                    spans.append(span)
                if failure:
                    basic_failures += 1
                active_start = None
                active_end = None

            if entity_type == target_type:
                active_start = start
                active_end = end

        elif prefix == "I":
            if entity_type == target_type:
                if active_start is not None:
                    active_end = end
                else:
                    active_start = start
                    active_end = end
            else:
                if active_start is not None and active_end is not None:
                    span, failure = _create_validated_span(
                        text, active_start, active_end, target_type
                    )
                    if span is not None:
                        spans.append(span)
                    if failure:
                        basic_failures += 1
                    active_start = None
                    active_end = None

        else:  # "O"
            if active_start is not None and active_end is not None:
                span, failure = _create_validated_span(
                    text, active_start, active_end, target_type
                )
                if span is not None:
                    spans.append(span)
                if failure:
                    basic_failures += 1
                active_start = None
                active_end = None

    if active_start is not None and active_end is not None:
        span, failure = _create_validated_span(
            text, active_start, active_end, target_type
        )
        if span is not None:
            spans.append(span)
        if failure:
            basic_failures += 1

    return (spans, basic_failures)


def _create_validated_span(
    text: str, start: int, end: int, entity_type: str
) -> tuple[EntitySpan | None, bool]:
    """Validate character span bounds against text and trim boundary whitespace."""
    if start < 0 or end > len(text) or start >= end:
        return (None, True)

    slice_str = text[start:end]
    l_strip = len(slice_str) - len(slice_str.lstrip())
    r_strip = len(slice_str) - len(slice_str.rstrip())

    adj_start = start + l_strip
    adj_end = end - r_strip

    if adj_start >= adj_end:
        return (None, True)

    try:
        span = EntitySpan(start=adj_start, end=adj_end, type=entity_type)
        return (span, False)
    except ValueError:
        return (None, True)


def parse_conll_data(
    content: str,
    *,
    strict: bool = True,
) -> list[tuple[list[str], list[str]]]:
    """Parse CoNLL text lines ('token|tag' or space-separated) with empty-line splits.

    Args:
        content: Raw file content string.
        strict: If True, fail loudly on malformed or incomplete lines.

    Returns:
        List of (tokens, tags) tuples per sentence.

    Raises:
        ValueError: If strict is True and a line is malformed.
    """
    sentences: list[tuple[list[str], list[str]]] = []
    current_tokens: list[str] = []
    current_tags: list[str] = []

    for line_idx, line in enumerate(content.splitlines(), start=1):
        line_clean = line.strip()
        if not line_clean:
            if current_tokens and current_tags:
                sentences.append((list(current_tokens), list(current_tags)))
                current_tokens.clear()
                current_tags.clear()
            continue

        if "|" in line_clean:
            token, _, tag = line_clean.rpartition("|")
            token_clean = token.strip()
            tag_clean = tag.strip()
            if not token_clean or not tag_clean:
                if strict:
                    raise ValueError(
                        f"Malformed CoNLL line at line {line_idx}: "
                        f"missing token or tag in '{line}'"
                    )
            else:
                current_tokens.append(token_clean)
                current_tags.append(tag_clean)
        else:
            parts = line_clean.split()
            if len(parts) == 2:
                current_tokens.append(parts[0])
                current_tags.append(parts[1])
            elif len(parts) > 2:
                current_tokens.append(parts[0])
                current_tags.append(parts[-1])
            else:
                if strict:
                    raise ValueError(
                        f"Malformed CoNLL line at line {line_idx}: "
                        f"unsupported shape in '{line}'"
                    )

    if current_tokens and current_tags:
        sentences.append((list(current_tokens), list(current_tags)))

    return sentences


@dataclass(frozen=True, slots=True)
class BenchmarkAggregateSummary:
    """Safe, privacy-conscious aggregate summary of a benchmark run.

    Contains only numerical and reproducibility metadata without source text,
    tokens, names, snippets, or raw predictions.
    """

    schema_version: str
    benchmark_protocol: str
    model_id: str
    model_revision: str
    model_license: str
    dataset_source: str
    dataset_source_kind: str
    dataset_revision: str
    dataset_split: str
    dataset_file_sha256: str
    original_dataset: str
    original_dataset_terms: str
    mirror_declared_license: str
    mirror_relicensing_authority: str
    package_redistribution_status: str
    evaluated_sentences: int
    gold_person_entities: int
    predicted_person_entities: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    boundary_errors: int
    pure_false_positives: int
    pure_false_negatives: int
    duplicate_predictions: int
    leading_i_recoveries: int
    basic_offset_validation_failures: int
    tokenizer_alignment_failures: int
    truncated_sentences: int
    max_tokenized_length: int
    sentences_with_zwnj: int
    gold_person_with_zwnj: int
    sentences_with_arabic_variants: int
    gold_person_with_arabic_variants: int
    python_version: str
    torch_version: str
    transformers_version: str
    tokenizers_version: str
    platform: str
    evaluation_policy: str

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregate summary to dictionary."""
        return {
            "schema_version": self.schema_version,
            "benchmark_protocol": self.benchmark_protocol,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "model_license": self.model_license,
            "dataset_source": self.dataset_source,
            "dataset_source_kind": self.dataset_source_kind,
            "dataset_revision": self.dataset_revision,
            "dataset_split": self.dataset_split,
            "dataset_file_sha256": self.dataset_file_sha256,
            "original_dataset": self.original_dataset,
            "original_dataset_terms": self.original_dataset_terms,
            "mirror_declared_license": self.mirror_declared_license,
            "mirror_relicensing_authority": self.mirror_relicensing_authority,
            "package_redistribution_status": self.package_redistribution_status,
            "evaluated_sentences": self.evaluated_sentences,
            "gold_person_entities": self.gold_person_entities,
            "predicted_person_entities": self.predicted_person_entities,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "boundary_errors": self.boundary_errors,
            "pure_false_positives": self.pure_false_positives,
            "pure_false_negatives": self.pure_false_negatives,
            "duplicate_predictions": self.duplicate_predictions,
            "leading_i_recoveries": self.leading_i_recoveries,
            "basic_offset_validation_failures": self.basic_offset_validation_failures,
            "tokenizer_alignment_failures": self.tokenizer_alignment_failures,
            "truncated_sentences": self.truncated_sentences,
            "max_tokenized_length": self.max_tokenized_length,
            "sentences_with_zwnj": self.sentences_with_zwnj,
            "gold_person_with_zwnj": self.gold_person_with_zwnj,
            "sentences_with_arabic_variants": self.sentences_with_arabic_variants,
            "gold_person_with_arabic_variants": self.gold_person_with_arabic_variants,
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "transformers_version": self.transformers_version,
            "tokenizers_version": self.tokenizers_version,
            "platform": self.platform,
            "evaluation_policy": self.evaluation_policy,
        }


def _validate_privacy_recursive(obj: Any) -> None:
    """Recursively validate that no sensitive or value-carrying keys exist."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in FORBIDDEN_RESULT_KEYS:
                raise ValueError(
                    f"Forbidden sensitive key '{k}' found in benchmark result"
                )
            _validate_privacy_recursive(v)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _validate_privacy_recursive(item)


def serialize_benchmark_result(
    summary: BenchmarkAggregateSummary | dict[str, Any],
) -> str:
    """Serialize benchmark results to deterministic, value-free JSON.

    Enforces strict recursive privacy gating: fails if any sensitive/value-carrying
    keys are present at any depth.

    Args:
        summary: BenchmarkAggregateSummary or result dictionary.

    Returns:
        Deterministic formatted JSON string.

    Raises:
        ValueError: If forbidden keys are present anywhere in the structure.
    """
    data = (
        summary.to_dict() if isinstance(summary, BenchmarkAggregateSummary) else summary
    )

    _validate_privacy_recursive(data)

    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)


def run_benchmark(
    dataset_file: str | Path,
    model_name_or_path: str = "HooshvareLab/bert-fa-base-uncased-ner-peyma",
    model_revision: str | None = "8b7b63371aa8f1fdad62c0f82d462a22b91b37ab",
    output_path: str | Path | None = None,
    *,
    offline: bool = True,
    max_length: int = 512,
) -> dict[str, Any]:
    """Execute the Persian NER benchmark reproducing exact PERSON span metrics.

    Lazy imports torch and transformers to keep base fa-redact dependency-free.

    Args:
        dataset_file: Path to local CoNLL test file.
        model_name_or_path: Hugging Face model identifier or local directory.
        model_revision: Pinned model commit hash.
        output_path: Optional path to write serialized aggregate JSON.
        offline: If True, require all assets to be present locally offline.
        max_length: Max sequence length for tokenizer auditing.

    Returns:
        Summary result dictionary.

    Raises:
        FileNotFoundError: If dataset file or model is not found.
        ValueError: If model configuration is missing required PERSON labels.
    """
    # Lazy imports of ML dependencies
    try:
        import tokenizers  # type: ignore[import-untyped]
        import torch
        import transformers  # type: ignore[import-untyped]
        from transformers import (
            AutoModelForTokenClassification,
            AutoTokenizer,
        )
    except ImportError as e:
        raise ImportError(
            "Research benchmark execution requires 'torch' and 'transformers'. "
            "Please install optional research dependencies."
        ) from e

    dataset_path = Path(dataset_file).expanduser().resolve()
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with open(dataset_path, "rb") as f:
        raw_bytes = f.read()
    dataset_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    content = raw_bytes.decode("utf-8")

    sentences = parse_conll_data(content, strict=True)
    if not sentences:
        raise ValueError(f"No sentences parsed from {dataset_path}")

    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(
        model_name_or_path,
        revision=model_revision,
        local_files_only=offline,
    )
    model = AutoModelForTokenClassification.from_pretrained(
        model_name_or_path,
        revision=model_revision,
        local_files_only=offline,
    )
    model.eval()

    # Validate model label map
    id2label: dict[int, str] = {
        int(k): str(v) for k, v in model.config.id2label.items()
    }
    label_values = set(id2label.values())

    # Check for PERSON labels
    has_b_per = any(
        lbl.upper() in ("B_PER", "B-PER", "B_PERSON", "B-PERSON")
        for lbl in label_values
    )
    has_i_per = any(
        lbl.upper() in ("I_PER", "I-PER", "I_PERSON", "I-PERSON")
        for lbl in label_values
    )
    if not (has_b_per and has_i_per):
        raise ValueError(
            f"Model {model_name_or_path} missing required PERSON labels: {id2label}"
        )

    # Accumulators
    total_gold_person = 0
    total_pred_person = 0
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_boundary_errors = 0
    total_pure_fp = 0
    total_pure_fn = 0
    total_duplicate_preds = 0
    total_leading_i_recoveries = 0
    total_basic_offset_failures = 0
    total_alignment_failures = 0
    truncated_sentences = 0
    max_tokenized_len = 0

    sentences_with_zwnj = 0
    gold_person_with_zwnj = 0
    sentences_with_arabic_variants = 0
    gold_person_with_arabic_variants = 0

    arabic_chars = ("\u064a", "\u0643")  # Arabic yeh, Arabic kaf

    with torch.no_grad():
        for tokens, tags in sentences:
            text, gold_spans, leading_i = bio_tokens_to_spans_with_stats(
                tokens, tags, target_type="PERSON"
            )
            total_leading_i_recoveries += leading_i
            total_gold_person += len(gold_spans)

            # Audit Unicode phenomena
            if "\u200c" in text:
                sentences_with_zwnj += 1
            if any(ar in text for ar in arabic_chars):
                sentences_with_arabic_variants += 1

            for g in gold_spans:
                g_text = text[g.start : g.end]
                if "\u200c" in g_text:
                    gold_person_with_zwnj += 1
                if any(ar in g_text for ar in arabic_chars):
                    gold_person_with_arabic_variants += 1

            # Tokenize for sequence length check
            full_encoding = tokenizer(
                text,
                return_offsets_mapping=True,
                add_special_tokens=True,
            )
            seq_len = len(full_encoding["input_ids"])
            if seq_len > max_tokenized_len:
                max_tokenized_len = seq_len
            if seq_len > max_length:
                truncated_sentences += 1

            # Model inference tokenization
            encoding = tokenizer(
                text,
                return_offsets_mapping=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            input_ids = encoding["input_ids"]
            attention_mask = encoding["attention_mask"]
            token_offsets = encoding["offset_mapping"][0].tolist()

            # Audit tokenizer alignment
            align_fails = audit_tokenizer_alignment(text, token_offsets)
            total_alignment_failures += align_fails

            # Forward pass
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits[0]
            pred_indices = torch.argmax(logits, dim=-1).tolist()
            pred_labels = [
                id2label.get(idx, "O") for idx in pred_indices[: len(token_offsets)]
            ]

            # Convert subwords to spans
            pred_spans, basic_fails = subwords_to_entity_spans(
                text, token_offsets, pred_labels, target_type="PERSON"
            )
            total_basic_offset_failures += basic_fails
            total_pred_person += len(pred_spans)

            # Evaluate sentence exact spans
            metrics = evaluate_exact_spans(gold_spans, pred_spans)
            total_tp += metrics.true_positives
            total_fp += metrics.false_positives
            total_fn += metrics.false_negatives

            # Error categorization
            error_analysis = analyze_errors(gold_spans, pred_spans)
            n_boundary = len(error_analysis.boundary_errors)
            total_boundary_errors += n_boundary
            total_pure_fp += max(0, len(error_analysis.false_positives) - n_boundary)
            total_pure_fn += max(0, len(error_analysis.false_negatives) - n_boundary)

    # Compute aggregate metrics
    prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

    summary = BenchmarkAggregateSummary(
        schema_version="1.1.0",
        benchmark_protocol="PERSON-only entity-level exact-span",
        model_id=str(model_name_or_path),
        model_revision=str(model_revision or ""),
        model_license="Apache-2.0",
        dataset_source="ParsiAI/PEYMA",
        dataset_source_kind="community_mirror",
        dataset_revision="c9995786945706010f000d4196b0a9ecbd6b96c5",
        dataset_split="test",
        dataset_file_sha256=dataset_sha256,
        original_dataset="PEYMA",
        original_dataset_terms="free for research purposes (authors)",
        mirror_declared_license="Apache-2.0",
        mirror_relicensing_authority="not_verified",
        package_redistribution_status="requires_verification",
        evaluated_sentences=len(sentences),
        gold_person_entities=total_gold_person,
        predicted_person_entities=total_pred_person,
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        precision=prec,
        recall=rec,
        f1=f1,
        boundary_errors=total_boundary_errors,
        pure_false_positives=total_pure_fp,
        pure_false_negatives=total_pure_fn,
        duplicate_predictions=total_duplicate_preds,
        leading_i_recoveries=total_leading_i_recoveries,
        basic_offset_validation_failures=total_basic_offset_failures,
        tokenizer_alignment_failures=total_alignment_failures,
        truncated_sentences=truncated_sentences,
        max_tokenized_length=max_tokenized_len,
        sentences_with_zwnj=sentences_with_zwnj,
        gold_person_with_zwnj=gold_person_with_zwnj,
        sentences_with_arabic_variants=sentences_with_arabic_variants,
        gold_person_with_arabic_variants=gold_person_with_arabic_variants,
        python_version=platform.python_version(),
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        tokenizers_version=tokenizers.__version__,
        platform=platform.platform(),
        evaluation_policy="exact_span_entity_level",
    )

    serialized = serialize_benchmark_result(summary)
    result_dict = summary.to_dict()

    if output_path is not None:
        out_file = Path(output_path).expanduser().resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(serialized + "\n")

    return result_dict


def main() -> None:
    """CLI entrypoint for running the Persian NER benchmark."""
    parser = argparse.ArgumentParser(
        description="Run Persian NER empirical exact-span benchmark."
    )
    parser.add_argument(
        "--dataset-file",
        required=True,
        help="Path to local CoNLL test dataset file (e.g. peyma_test.txt)",
    )
    parser.add_argument(
        "--model",
        default="HooshvareLab/bert-fa-base-uncased-ner-peyma",
        help="Hugging Face model ID or local directory path",
    )
    parser.add_argument(
        "--model-revision",
        default="8b7b63371aa8f1fdad62c0f82d462a22b91b37ab",
        help="Pinned commit hash of the model",
    )
    parser.add_argument(
        "--output",
        default="research/results/phase21_1_persian_ner_benchmark.json",
        help="Path to output serialized aggregate JSON",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="Enforce local files only without network requests (default: True)",
    )
    parser.add_argument(
        "--online",
        dest="offline",
        action="store_false",
        help="Allow online downloads if assets are not cached",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Maximum sequence length for tokenization",
    )

    args = parser.parse_args()

    res = run_benchmark(
        dataset_file=args.dataset_file,
        model_name_or_path=args.model,
        model_revision=args.model_revision,
        output_path=args.output,
        offline=args.offline,
        max_length=args.max_length,
    )

    print("========================================")
    print("PERSIAN NER EXACT-SPAN BENCHMARK COMPLETE")
    print("========================================")
    print(f"Evaluated sentences: {res['evaluated_sentences']}")
    print(f"Gold PERSON entities: {res['gold_person_entities']}")
    print(f"Predicted PERSON entities: {res['predicted_person_entities']}")
    print(
        f"TP: {res['true_positives']} | "
        f"FP: {res['false_positives']} | "
        f"FN: {res['false_negatives']}"
    )
    print(f"Precision: {res['precision']:.6f}")
    print(f"Recall:    {res['recall']:.6f}")
    print(f"F1:        {res['f1']:.6f}")
    print(f"Boundary errors: {res['boundary_errors']}")
    print(
        f"Pure FPs: {res['pure_false_positives']} | "
        f"Pure FNs: {res['pure_false_negatives']}"
    )
    print(
        f"Basic offset validation failures: {res['basic_offset_validation_failures']}"
    )
    print(f"Tokenizer alignment failures: {res['tokenizer_alignment_failures']}")
    print(f"Truncated sentences: {res['truncated_sentences']}")
    print(f"Max tokenized sequence length: {res['max_tokenized_length']}")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
