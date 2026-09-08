"""Comprehensive independent benchmark runner for Phase 29 Persian PII ecosystem audit.

===============================================================================
PRIVACY & RESEARCH SAFETY GUARANTEES:
1. Metadata and aggregate statistics ONLY.
2. ZERO source_text, raw entity values, PII snippets, or patient text are exported.
3. Isolated to research/ and does NOT modify production src/ or package dependencies.
4. All test identifiers generated dynamically via deterministic checksum algorithms.
===============================================================================
"""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from research.evaluation import EntitySpan, calculate_metrics
from research.phase29_adapters import (
    BenchmarkAdapter,
    FaRedactCurrentHybridAdapter,
    FaRedactCurrentNERAdapter,
    FaRedactDeterministicAdapter,
    OpenMedONNXAdapter,
    ParsiKitAdapter,
    PersianToolsAdapter,
    canonicalize_gold_spans,
)
from research.phase29_challenge_set import (
    ChallengeDocument,
    _generate_valid_bank_card,
    _generate_valid_national_id,
    build_dataset_b,
    build_dataset_c,
)

# Common direct identifier capability taxonomy subset
COMMON_DIRECT_ID_TYPES: set[str] = {
    "IR_NATIONAL_ID",
    "IR_MOBILE",
    "IR_IBAN",
    "BANK_CARD",
    "IR_LEGAL_ENTITY_ID",
    "EMAIL",
}


@dataclass(frozen=True, slots=True)
class EvaluationStats:
    """Exact-span, relaxed, leakage, and error metrics for an evaluation run."""

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    total_gold: int
    total_predicted: int
    relaxed_precision: float
    relaxed_recall: float
    relaxed_f1: float
    entity_leakage_rate: float
    document_leakage_rate: float
    documents_with_fp: int
    doc_fp_rate: float
    offset_failures: int
    offset_failure_rate: float
    adapter_error_count: int
    affected_document_count: int
    exception_type_counts: dict[str, int]
    per_type: dict[str, dict[str, float]]


def evaluate_predictions(
    cases_with_preds: Sequence[tuple[str, list[EntitySpan], list[EntitySpan]]],
    target_types_filter: set[str] | None = None,
    error_metadata: dict[str, Any] | None = None,
) -> EvaluationStats:
    """Evaluate pre-computed predictions against gold spans over
    a collection of test cases.
    """
    exact_tp = 0
    exact_fp = 0
    exact_fn = 0

    relaxed_tp = 0
    relaxed_fp = 0
    relaxed_fn = 0

    total_gold = 0
    total_predicted = 0

    offset_failures = 0
    total_predictions = 0

    missed_docs = 0
    docs_with_pii = 0
    docs_with_fp = 0
    total_docs = len(cases_with_preds)

    type_gold_counts: Counter[str] = Counter()
    type_pred_counts: Counter[str] = Counter()
    type_tp_counts: Counter[str] = Counter()
    type_fp_counts: Counter[str] = Counter()
    type_fn_counts: Counter[str] = Counter()

    for text, gold_spans, preds in cases_with_preds:
        if target_types_filter is not None:
            filtered_gold = [s for s in gold_spans if s.type in target_types_filter]
            filtered_preds = [p for p in preds if p.type in target_types_filter]
        else:
            filtered_gold = list(gold_spans)
            filtered_preds = list(preds)

        has_pii = len(filtered_gold) > 0
        if has_pii:
            docs_with_pii += 1

        # Validate offset integrity
        for p in filtered_preds:
            total_predictions += 1
            if not (0 <= p.start < p.end <= len(text)):
                offset_failures += 1
            elif not text[p.start : p.end].strip():
                offset_failures += 1

        # Exact matching
        gold_set = set(filtered_gold)
        pred_set = set(filtered_preds)

        tp_set = gold_set.intersection(pred_set)
        fp_set = pred_set - gold_set
        fn_set = gold_set - pred_set

        exact_tp += len(tp_set)
        exact_fp += len(fp_set)
        exact_fn += len(fn_set)

        total_gold += len(filtered_gold)
        total_predicted += len(filtered_preds)

        if len(fn_set) > 0 and has_pii:
            missed_docs += 1
        if len(fp_set) > 0:
            docs_with_fp += 1

        for s in filtered_gold:
            type_gold_counts[s.type] += 1
        for p in filtered_preds:
            type_pred_counts[p.type] += 1
        for tp in tp_set:
            type_tp_counts[tp.type] += 1
        for fp in fp_set:
            type_fp_counts[fp.type] += 1
        for fn in fn_set:
            type_fn_counts[fn.type] += 1

        # Relaxed matching (span overlap with matching label)
        matched_gold_idx: set[int] = set()
        matched_pred_idx: set[int] = set()

        for p_idx, p in enumerate(filtered_preds):
            for g_idx, g in enumerate(filtered_gold):
                if g_idx in matched_gold_idx:
                    continue
                if p.type == g.type and max(p.start, g.start) < min(p.end, g.end):
                    matched_gold_idx.add(g_idx)
                    matched_pred_idx.add(p_idx)
                    break

        relaxed_tp += len(matched_gold_idx)
        relaxed_fp += len(filtered_preds) - len(matched_pred_idx)
        relaxed_fn += len(filtered_gold) - len(matched_gold_idx)

    prec, rec, f1 = calculate_metrics(exact_tp, exact_fp, exact_fn)
    r_prec, r_rec, r_f1 = calculate_metrics(relaxed_tp, relaxed_fp, relaxed_fn)

    entity_leakage = (exact_fn / total_gold) if total_gold > 0 else 0.0
    doc_leakage = (missed_docs / docs_with_pii) if docs_with_pii > 0 else 0.0
    doc_fp_rate = (docs_with_fp / total_docs) if total_docs > 0 else 0.0
    offset_fail_rate = (
        (offset_failures / total_predictions) if total_predictions > 0 else 0.0
    )

    per_type_metrics: dict[str, dict[str, float]] = {}
    all_types = set(type_gold_counts.keys()).union(type_pred_counts.keys())
    for t in sorted(all_types):
        t_tp = type_tp_counts[t]
        t_fp = type_fp_counts[t]
        t_fn = type_fn_counts[t]
        tp_prec, tp_rec, tp_f1 = calculate_metrics(t_tp, t_fp, t_fn)
        per_type_metrics[t] = {
            "tp": t_tp,
            "fp": t_fp,
            "fn": t_fn,
            "gold": type_gold_counts[t],
            "predicted": type_pred_counts[t],
            "precision": round(tp_prec, 4),
            "recall": round(tp_rec, 4),
            "f1": round(tp_f1, 4),
        }

    err_meta = error_metadata or {}

    return EvaluationStats(
        true_positives=exact_tp,
        false_positives=exact_fp,
        false_negatives=exact_fn,
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        total_gold=total_gold,
        total_predicted=total_predicted,
        relaxed_precision=round(r_prec, 4),
        relaxed_recall=round(r_rec, 4),
        relaxed_f1=round(r_f1, 4),
        entity_leakage_rate=round(entity_leakage, 4),
        document_leakage_rate=round(doc_leakage, 4),
        documents_with_fp=docs_with_fp,
        doc_fp_rate=round(doc_fp_rate, 4),
        offset_failures=offset_failures,
        offset_failure_rate=round(offset_fail_rate, 4),
        adapter_error_count=err_meta.get("adapter_error_count", 0),
        affected_document_count=err_meta.get("affected_document_count", 0),
        exception_type_counts=err_meta.get("exception_type_counts", {}),
        per_type=per_type_metrics,
    )


def run_adapter_inference(
    adapter: Any,
    cases: Sequence[ChallengeDocument | dict[str, Any]],
    canonicalize_gold: bool = True,
    use_raw_adapter_predictions: bool = False,
) -> tuple[
    list[tuple[str, list[EntitySpan], list[EntitySpan]]],
    dict[str, Any],
    dict[str, Any],
]:
    """Run single-pass inference across cases and collect predictions,
    latency, and error metadata.
    """
    latencies: list[float] = []
    cases_with_preds: list[tuple[str, list[EntitySpan], list[EntitySpan]]] = []

    adapter_error_count = 0
    affected_doc_ids: set[str] = set()
    exception_type_counts: Counter[str] = Counter()

    for idx, case in enumerate(cases):
        if isinstance(case, ChallengeDocument):
            doc_id = case.doc_id
            text = case.text
            if canonicalize_gold:
                gold_spans = canonicalize_gold_spans(text, case.gold_spans)
            else:
                gold_spans = list(case.gold_spans)
        else:
            doc_id = str(case.get("uid", f"doc_{idx}"))
            text = str(case["source_text"])
            raw_mask = case.get("privacy_mask")
            if raw_mask is None:
                raw_mask = []
            if canonicalize_gold:
                gold_spans = canonicalize_gold_spans(text, raw_mask)
            else:
                gold_spans = [
                    EntitySpan(
                        start=int(item["start"]),
                        end=int(item["end"]),
                        type=item["label"],
                    )
                    for item in raw_mask
                ]

        preds: list[EntitySpan] = []
        t0 = time.perf_counter()
        try:
            if use_raw_adapter_predictions and hasattr(adapter, "detect_raw_spans"):
                preds = adapter.detect_raw_spans(text)
            else:
                preds = adapter.detect_spans(text)
        except Exception as e:
            adapter_error_count += 1
            affected_doc_ids.add(doc_id)
            exception_type_counts[type(e).__name__] += 1
            preds = []
        dt = time.perf_counter() - t0
        latencies.append(dt)

        cases_with_preds.append((text, gold_spans, preds))

    perf_stats = {
        "median_latency_ms": round(sorted(latencies)[len(latencies) // 2] * 1000, 2)
        if latencies
        else 0.0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 2)
        if latencies
        else 0.0,
        "total_time_s": round(sum(latencies), 2),
        "docs_per_second": round(len(cases) / sum(latencies), 2)
        if sum(latencies) > 0
        else 0.0,
    }

    error_metadata = {
        "adapter_error_count": adapter_error_count,
        "affected_document_count": len(affected_doc_ids),
        "exception_type_counts": dict(exception_type_counts),
    }

    return cases_with_preds, perf_stats, error_metadata


def run_long_document_benchmark(adapters: list[Any]) -> dict[str, Any]:
    """Test long document handling with ~256, ~512, and ~1000 token inputs."""
    long_results: dict[str, Any] = {}

    nid_cand = _generate_valid_national_id(991)
    mob_cand = "0912" + f"{(991 * 12345 + 1000000) % 9000000 + 1000000:07d}"
    card_cand = _generate_valid_bank_card(991)

    p_start = f"بیمار علی رضایی با کدملی {nid_cand} در بخش پذیرش شد. "
    filler_para = (
        "پزشک معالج وضعیت عمومی بیمار را بررسی نمود و دستورات لازم جهت "
        "مراقبت‌های بالینی و پایش علائم حیاتی را صادر کرد. "
    )
    p_mid = f"شماره همراه همراه بیمار {mob_cand} جهت تماس ضروری ثبت گردید. "
    p_end = f"تسویه حساب نهایی به شماره کارت {card_cand} انجام پذیرفت."

    configs = [
        ("256_tokens_approx", p_start + (filler_para * 3) + p_mid + p_end),
        (
            "512_tokens_approx",
            p_start + (filler_para * 8) + p_mid + (filler_para * 2) + p_end,
        ),
        (
            "1000_tokens_approx",
            p_start + (filler_para * 18) + p_mid + (filler_para * 4) + p_end,
        ),
    ]

    for len_name, txt in configs:
        long_results[len_name] = {
            "char_length": len(txt),
            "estimated_tokens": len(txt.split()),
            "systems": {},
        }
        for a in adapters:
            if not a.is_available:
                continue
            t0 = time.perf_counter()
            try:
                spans = a.detect_spans(txt)
                dt = time.perf_counter() - t0
                long_results[len_name]["systems"][a.adapter_id] = {
                    "detected_spans_count": len(spans),
                    "detected_types": sorted(list(set(s.type for s in spans))),
                    "latency_ms": round(dt * 1000, 2),
                    "offset_valid": all(
                        0 <= s.start < s.end <= len(txt) for s in spans
                    ),
                    "status": "SUCCESS",
                }
            except Exception as e:
                dt = time.perf_counter() - t0
                long_results[len_name]["systems"][a.adapter_id] = {
                    "detected_spans_count": 0,
                    "detected_types": [],
                    "latency_ms": round(dt * 1000, 2),
                    "offset_valid": True,
                    "status": f"FAILED: {type(e).__name__}",
                    "error_note": (
                        f"Exceeded input limit or engine error ({type(e).__name__})"
                    ),
                }

    return long_results


def run_reproducibility_benchmark(
    adapters: list[Any],
) -> dict[str, Any]:
    """Run 3 identical passes and verify if predictions are completely deterministic."""
    repro_results: dict[str, Any] = {}
    nid = _generate_valid_national_id(882)
    card = _generate_valid_bank_card(882)
    mob = "0912" + f"{(882 * 12345 + 1000000) % 9000000 + 1000000:07d}"

    sample_text = (
        f"بیمار علی رضایی به شماره ملی {nid} و تلفن همراه {mob} با ایمیل "
        f"ali.rezaei@example.com جهت واریز به کارت {card} مراجعه نمود."
    )

    for a in adapters:
        if not a.is_available:
            continue
        runs = []
        try:
            for _ in range(3):
                spans = a.detect_spans(sample_text)
                runs.append([(s.start, s.end, s.type) for s in spans])
            is_deterministic = runs[0] == runs[1] == runs[2]
            repro_results[a.adapter_id] = {
                "deterministic": is_deterministic,
                "span_count_run1": len(runs[0]),
                "span_count_run2": len(runs[1]),
                "span_count_run3": len(runs[2]),
                "status": "SUCCESS",
            }
        except Exception as e:
            repro_results[a.adapter_id] = {
                "deterministic": False,
                "span_count_run1": 0,
                "span_count_run2": 0,
                "span_count_run3": 0,
                "status": f"FAILED: {type(e).__name__}",
            }
    return repro_results


def run_benchmark_suite(
    reproduction_sample_limit: int = 100,
) -> dict[str, Any]:
    """Run corrected Phase 29 Persian PII Ecosystem Benchmark."""
    print("Initializing Phase 29 Benchmark Suite...")

    adapters: list[BenchmarkAdapter] = [
        FaRedactDeterministicAdapter(),
        FaRedactCurrentNERAdapter(),
        FaRedactCurrentHybridAdapter(),
        OpenMedONNXAdapter(
            "Reza2kn/openmed-persian-pii-tookabert-large-onnx-int4",
            "TookaBERT Large",
            mode="wrapper",
        ),
        OpenMedONNXAdapter(
            "Reza2kn/openmed-persian-pii-google-mbert-onnx-int4",
            "Google mBERT",
            mode="wrapper",
        ),
        ParsiKitAdapter(),
        PersianToolsAdapter(),
    ]

    print(f"Adapters initialized: {len(adapters)}")
    for a in adapters:
        status = (
            "AVAILABLE"
            if a.is_available
            else f"UNAVAILABLE ({getattr(a, '_load_error', 'N/A')})"
        )
        print(f"  - {a.display_name}: {status}")

    # Load Challenge sets B and C
    print("\nLoading Challenge Sets B and C...")
    dataset_b = build_dataset_b()
    dataset_c = build_dataset_c()

    n_gold_b = sum(len(d.gold_spans) for d in dataset_b)
    n_gold_c = sum(len(d.gold_spans) for d in dataset_c)
    print(f"Dataset B: {len(dataset_b)} documents, {n_gold_b} gold entities")
    print(f"Dataset C: {len(dataset_c)} documents, {n_gold_c} gold entities")

    # Load Dataset A reproduction sample (100 rows)
    print(
        f"\nLoading Dataset A reproduction sample ({reproduction_sample_limit} rows)..."
    )
    dataset_a: list[dict[str, Any]] = []
    try:
        import pandas as pd  # type: ignore[import-untyped]
        from huggingface_hub import hf_hub_download

        test_path = ""
        try:
            test_path = hf_hub_download(
                repo_id="Reza2kn/persian-pii-masking-openpii-690k-clean",
                filename="data/test-00000-of-00001.parquet",
                repo_type="dataset",
                local_files_only=True,
            )
        except Exception:
            test_path = hf_hub_download(
                repo_id="Reza2kn/persian-pii-masking-openpii-690k-clean",
                filename="data/test-00000-of-00001.parquet",
                repo_type="dataset",
            )

        if test_path and Path(test_path).exists():
            df_test = pd.read_parquet(test_path)
            sample_df = df_test.iloc[:reproduction_sample_limit]
            for _, row in sample_df.iterrows():
                dataset_a.append(
                    {
                        "source_text": row["source_text"],
                        "privacy_mask": row["privacy_mask"],
                        "uid": row.get("uid", ""),
                    }
                )
            print(f"Dataset A loaded: {len(dataset_a)} rows")
    except Exception as err:
        print(f"Dataset A failed to load: {err}")

    results: dict[str, Any] = {
        "benchmark_name": "Phase 29 Persian PII Ecosystem Audit & Benchmark",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datasets": {
            "dataset_a_reproduction": {
                "dataset_id": "Reza2kn/persian-pii-masking-openpii-690k-clean",
                "split": "test",
                "sample_rows": len(dataset_a),
                "selection": "first_100_deterministic",
            },
            "dataset_b_independent": {
                "name": "Independent Persian Synthetic Challenge Set",
                "documents_count": len(dataset_b),
                "gold_entities_count": sum(len(d.gold_spans) for d in dataset_b),
            },
            "dataset_c_clinical": {
                "name": "Iranian Clinical-Style Synthetic Challenge Set",
                "documents_count": len(dataset_c),
                "gold_entities_count": sum(len(d.gold_spans) for d in dataset_c),
            },
        },
        "evaluations": {
            "dataset_a_publisher_reproduction": {},
            "dataset_a_canonical_exact_span": {},
            "dataset_b_all_entities": {},
            "dataset_b_common_capabilities": {},
            "dataset_b_person_only": {},
            "dataset_c_all_entities": {},
            "dataset_c_common_capabilities": {},
            "dataset_c_person_only": {},
        },
        "long_document": {},
        "reproducibility": {},
    }

    # 1. Run Dataset A
    print("\n=== Running Dataset A Evaluations ===")
    if dataset_a:
        for adapter in adapters:
            if not adapter.is_available:
                continue
            print(f"Evaluating {adapter.display_name} on Dataset A...")

            # A. Publisher reproduction metric (raw labels where supported)
            if isinstance(adapter, OpenMedONNXAdapter):
                raw_cases, perf_raw, err_raw = run_adapter_inference(
                    adapter,
                    dataset_a,
                    canonicalize_gold=False,
                    use_raw_adapter_predictions=True,
                )
                raw_stats = evaluate_predictions(raw_cases, error_metadata=err_raw)
                results["evaluations"]["dataset_a_publisher_reproduction"][
                    adapter.adapter_id
                ] = {
                    "display_name": f"{adapter.display_name} [Raw 19-Label Exact-Span]",
                    "metrics": asdict(raw_stats),
                    "performance": perf_raw,
                    "reproducibility_status": (
                        "Evaluated as exact character-span on raw publisher "
                        "labels without private subword alignment script. "
                        "Publisher model card reported token-level macro F1 "
                        "(~0.98 TookaBERT / ~0.97 mBERT) is NOT EXACTLY "
                        "REPRODUCIBLE at raw character level without "
                        "publisher internal token-classification pipeline."
                    ),
                }

            # B. Canonical exact-span metric (symmetrically mapped and merged)
            can_cases, perf_can, err_can = run_adapter_inference(
                adapter,
                dataset_a,
                canonicalize_gold=True,
                use_raw_adapter_predictions=False,
            )
            can_stats = evaluate_predictions(can_cases, error_metadata=err_can)
            results["evaluations"]["dataset_a_canonical_exact_span"][
                adapter.adapter_id
            ] = {
                "display_name": adapter.display_name,
                "metrics": asdict(can_stats),
                "performance": perf_can,
            }

    # 2. Run Dataset B (Single-Pass Inference per Adapter)
    print("\n=== Running Dataset B Evaluations (Single-Pass Deduplicated) ===")
    for adapter in adapters:
        if not adapter.is_available:
            continue
        print(f"Evaluating {adapter.display_name} on Dataset B...")
        cases_with_preds, perf, err_meta = run_adapter_inference(
            adapter, dataset_b, canonicalize_gold=True
        )

        # View 1: All Entities
        stats_all = evaluate_predictions(cases_with_preds, error_metadata=err_meta)
        results["evaluations"]["dataset_b_all_entities"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_all),
            "performance": perf,
        }

        # View 2: Common Direct-ID Capabilities
        stats_com = evaluate_predictions(
            cases_with_preds,
            target_types_filter=COMMON_DIRECT_ID_TYPES,
            error_metadata=err_meta,
        )
        results["evaluations"]["dataset_b_common_capabilities"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_com),
        }

        # View 3: Dedicated PERSON-only comparison
        stats_per = evaluate_predictions(
            cases_with_preds,
            target_types_filter={"PERSON"},
            error_metadata=err_meta,
        )
        results["evaluations"]["dataset_b_person_only"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_per),
        }

    # 3. Run Dataset C (Single-Pass Inference per Adapter)
    print("\n=== Running Dataset C Evaluations (Single-Pass Deduplicated) ===")
    for adapter in adapters:
        if not adapter.is_available:
            continue
        print(f"Evaluating {adapter.display_name} on Dataset C...")
        cases_with_preds, perf, err_meta = run_adapter_inference(
            adapter, dataset_c, canonicalize_gold=True
        )

        # View 1: All Entities
        stats_all = evaluate_predictions(cases_with_preds, error_metadata=err_meta)
        results["evaluations"]["dataset_c_all_entities"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_all),
            "performance": perf,
        }

        # View 2: Common Direct-ID Capabilities
        stats_com = evaluate_predictions(
            cases_with_preds,
            target_types_filter=COMMON_DIRECT_ID_TYPES,
            error_metadata=err_meta,
        )
        results["evaluations"]["dataset_c_common_capabilities"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_com),
        }

        # View 3: Dedicated PERSON-only comparison
        stats_per = evaluate_predictions(
            cases_with_preds,
            target_types_filter={"PERSON"},
            error_metadata=err_meta,
        )
        results["evaluations"]["dataset_c_person_only"][adapter.adapter_id] = {
            "display_name": adapter.display_name,
            "metrics": asdict(stats_per),
        }

    # 4. Long Document Benchmark
    print("\n=== Running Long Document Benchmark ===")
    results["long_document"] = run_long_document_benchmark(adapters)

    # 5. Reproducibility Benchmark
    print("\n=== Running Reproducibility Benchmark ===")
    results["reproducibility"] = run_reproducibility_benchmark(adapters)

    print("\nBenchmark Suite completed successfully!")
    return results


if __name__ == "__main__":
    out_dir = Path("research/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    benchmark_data = run_benchmark_suite(reproduction_sample_limit=100)

    out_file = out_dir / "phase29_persian_pii_benchmark.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {out_file}")
