"""Persian Named Entity Recognition (NER) empirical benchmark runner.

This module provides deterministic utilities for:
1. Reconstructing text and gold character spans from token/BIO sequences.
2. Mapping fast tokenizer subword predictions and character offsets to exact
   original-text entity spans.
3. Evaluating PERSON exact-span precision, recall, and F1.
4. Serializing value-free, privacy-safe benchmark aggregate results.

Zero runtime dependencies are required for the utility functions.
Model execution requires optional research dependencies (transformers, torch).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from research.evaluation import EntitySpan

# Standard PERSON label identifiers
PERSON_LABEL_SET: frozenset[str] = frozenset(
    {"PER", "PERS", "PERSON", "Person", "person"}
)


def parse_bio_label(label: str) -> tuple[str, str | None]:
    """Parse a BIO/IOB tag into prefix ('B', 'I', 'O') and entity type.

    Accepts delimiters '_' and '-' (e.g. 'B_PER', 'B-PER', 'I_PER', 'O').
    Maps person-related type labels (PER, PERS, Person, person) to 'PERSON'.

    Args:
        label: Raw label string.

    Returns:
        Tuple of (prefix, normalized_entity_type).
        If prefix is 'O', entity_type is None.
    """
    clean_label = label.strip()
    if not clean_label or clean_label == "O":
        return ("O", None)

    # Handle B_PER, B-PER, I_PER, I-PER, etc.
    if "_" in clean_label:
        prefix, _, raw_type = clean_label.partition("_")
    elif "-" in clean_label:
        prefix, _, raw_type = clean_label.partition("-")
    else:
        # Fallback for bare prefix or label
        prefix = clean_label[0] if clean_label[0] in ("B", "I", "O") else "B"
        raw_type = clean_label[1:] if clean_label[0] in ("B", "I") else clean_label

    prefix = prefix.upper()
    if prefix not in ("B", "I", "O"):
        prefix = "B"

    raw_type_clean = raw_type.strip()
    if not raw_type_clean or prefix == "O":
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
    - 'I-<TYPE>' without a preceding matching B (leading I) is treated as starting
      a new entity (lenient BIO recovery).
    - Consecutive 'B-<TYPE>' tags are treated as two distinct contiguous entities.
    - 'O' or type transitions close the active entity.

    Args:
        tokens: Sequence of token strings.
        tags: Sequence of BIO tag strings (e.g. 'B_PER', 'I_PER', 'O').
        target_type: Entity type to isolate (defaults to 'PERSON').

    Returns:
        Tuple of (reconstructed_text, entity_spans).

    Raises:
        ValueError: If len(tokens) != len(tags).
    """
    if len(tokens) != len(tags):
        raise ValueError(
            f"Tokens and tags length mismatch: {len(tokens)} != {len(tags)}"
        )

    if not tokens:
        return ("", [])

    # Reconstruct text and compute token offsets
    token_offsets: list[tuple[int, int]] = []
    current_pos = 0
    text_parts: list[str] = []

    for i, tok in enumerate(tokens):
        if i > 0:
            current_pos += 1  # Account for space separator
        start = current_pos
        end = start + len(tok)
        token_offsets.append((start, end))
        current_pos = end
        text_parts.append(tok)

    reconstructed_text = " ".join(text_parts)

    # Extract spans for target_type
    spans: list[EntitySpan] = []
    active_start: int | None = None
    active_end: int | None = None

    for i, tag in enumerate(tags):
        prefix, entity_type = parse_bio_label(tag)
        tok_start, tok_end = token_offsets[i]

        if prefix == "B":
            # Close existing active span if any
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
                    # Continue existing entity
                    active_end = tok_end
                else:
                    # Leading I-tag: recover as starting a new entity
                    active_start = tok_start
                    active_end = tok_end
            else:
                # Different entity type closes current target entity
                if active_start is not None and active_end is not None:
                    spans.append(
                        EntitySpan(start=active_start, end=active_end, type=target_type)
                    )
                    active_start = None
                    active_end = None

        else:  # prefix == "O"
            if active_start is not None and active_end is not None:
                spans.append(
                    EntitySpan(start=active_start, end=active_end, type=target_type)
                )
                active_start = None
                active_end = None

    # Close trailing entity if active
    if active_start is not None and active_end is not None:
        spans.append(EntitySpan(start=active_start, end=active_end, type=target_type))

    # Verify that all extracted spans slice valid non-empty substrings
    for span in spans:
        slice_str = reconstructed_text[span.start : span.end]
        if not slice_str or slice_str.strip() == "":
            raise ValueError(
                f"Invalid empty slice for reconstructed span ({span.start}, {span.end})"
            )

    return (reconstructed_text, spans)


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
        text: Original evaluated text string.
        token_offsets: List of (start, end) character offsets from fast tokenizer.
        predicted_labels: List of predicted tag strings for each subword token.
        target_type: Target entity type to extract (default 'PERSON').

    Returns:
        Tuple of (predicted_spans, offset_mapping_failures).
    """
    if len(token_offsets) != len(predicted_labels):
        raise ValueError(
            f"Offset and label length mismatch: {len(token_offsets)} "
            f"!= {len(predicted_labels)}"
        )

    spans: list[EntitySpan] = []
    mapping_failures = 0

    active_start: int | None = None
    active_end: int | None = None

    for offset, label in zip(token_offsets, predicted_labels, strict=True):
        start, end = offset
        # Skip special tokens (start == end)
        if start == end:
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
                    mapping_failures += 1
                active_start = None
                active_end = None

            if entity_type == target_type:
                active_start = start
                active_end = end

        elif prefix == "I":
            if entity_type == target_type:
                if active_start is not None:
                    # Extend span
                    active_end = end
                else:
                    # Leading I token: start new span
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
                        mapping_failures += 1
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
                    mapping_failures += 1
                active_start = None
                active_end = None

    if active_start is not None and active_end is not None:
        span, failure = _create_validated_span(
            text, active_start, active_end, target_type
        )
        if span is not None:
            spans.append(span)
        if failure:
            mapping_failures += 1

    return (spans, mapping_failures)


def _create_validated_span(
    text: str, start: int, end: int, entity_type: str
) -> tuple[EntitySpan | None, bool]:
    """Validate character span bounds against text and trim boundary whitespace."""
    if start < 0 or end > len(text) or start >= end:
        return (None, True)

    # Trim leading/trailing whitespace if tokenizer included it in subword offset
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


def parse_conll_data(content: str) -> list[tuple[list[str], list[str]]]:
    """Parse CoNLL-formatted text lines ('token|tag') separated by empty lines.

    Args:
        content: Raw file content string.

    Returns:
        List of (tokens, tags) tuples per sentence.
    """
    sentences: list[tuple[list[str], list[str]]] = []
    current_tokens: list[str] = []
    current_tags: list[str] = []

    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean:
            if current_tokens and current_tags:
                sentences.append((list(current_tokens), list(current_tags)))
                current_tokens.clear()
                current_tags.clear()
            continue

        if "|" in line_clean:
            token, _, tag = line_clean.partition("|")
            token_clean = token.strip()
            tag_clean = tag.strip()
            if token_clean and tag_clean:
                current_tokens.append(token_clean)
                current_tags.append(tag_clean)
        elif "\t" in line_clean or " " in line_clean:
            parts = line_clean.split()
            if len(parts) >= 2:
                current_tokens.append(parts[0])
                current_tags.append(parts[-1])

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
    model_id: str
    model_revision: str
    model_license: str
    dataset: str
    dataset_revision: str
    dataset_license: str
    dataset_split: str
    evaluated_sentences: int
    gold_person_entities: int
    predicted_person_entities: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    offset_mapping_failures: int
    duplicate_predictions: int
    python_version: str
    benchmark_tool_versions: dict[str, str]
    evaluation_policy: str

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregate summary to dictionary."""
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "model_license": self.model_license,
            "dataset": self.dataset,
            "dataset_revision": self.dataset_revision,
            "dataset_license": self.dataset_license,
            "dataset_split": self.dataset_split,
            "evaluated_sentences": self.evaluated_sentences,
            "gold_person_entities": self.gold_person_entities,
            "predicted_person_entities": self.predicted_person_entities,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "offset_mapping_failures": self.offset_mapping_failures,
            "duplicate_predictions": self.duplicate_predictions,
            "python_version": self.python_version,
            "benchmark_tool_versions": self.benchmark_tool_versions,
            "evaluation_policy": self.evaluation_policy,
        }


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
    }
)


def serialize_benchmark_result(
    summary: BenchmarkAggregateSummary | dict[str, Any],
) -> str:
    """Serialize benchmark results to deterministic, value-free JSON.

    Enforces strict privacy gating: fails if any sensitive/value-carrying keys
    are present.

    Args:
        summary: BenchmarkAggregateSummary or result dictionary.

    Returns:
        Deterministic formatted JSON string.

    Raises:
        ValueError: If forbidden keys are present.
    """
    data = (
        summary.to_dict() if isinstance(summary, BenchmarkAggregateSummary) else summary
    )

    for key in data:
        if key.lower() in FORBIDDEN_RESULT_KEYS:
            raise ValueError(
                f"Forbidden sensitive key '{key}' found in benchmark result"
            )

    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)
