"""Command-line interface for fa-redact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from fa_redact import __version__
from fa_redact.conflicts import ConflictPolicy
from fa_redact.detectors import (
    BankCardDetector,
    EmailDetector,
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
)
from fa_redact.pipeline import detect
from fa_redact.protocols import Detector
from fa_redact.redaction import redact
from fa_redact.reporting import detection_report

_DETECTOR_MAP: dict[str, type[Detector]] = {
    "national_id": IranianNationalIDDetector,
    "national-id": IranianNationalIDDetector,
    "national": IranianNationalIDDetector,
    "ir_national_id": IranianNationalIDDetector,
    "mobile": IranianMobileNumberDetector,
    "ir_mobile": IranianMobileNumberDetector,
    "iban": IranianIBANDetector,
    "sheba": IranianIBANDetector,
    "ir_iban": IranianIBANDetector,
    "email": EmailDetector,
    "bank_card": BankCardDetector,
    "bank-card": BankCardDetector,
    "card": BankCardDetector,
    "bankcard": BankCardDetector,
}

_AVAILABLE_DETECTOR_NAMES = "national_id, mobile, iban, email, bank_card, none"


def _parse_detectors(detectors_arg: str | None) -> list[Detector] | None:
    """Parse comma-separated detector names into Detector instances.

    Returns None if detectors_arg is None (preserving library defaults).
    Returns an explicit list of Detector instances (or [] for none/empty)
    which replaces default detectors.
    """
    if detectors_arg is None:
        return None

    raw_items = [item.strip() for item in detectors_arg.split(",")]
    cleaned_items = [item for item in raw_items if item]

    if not cleaned_items:
        return []

    active_detectors: list[Detector] = []
    for item in cleaned_items:
        key = item.lower()
        if key in ("none", "empty"):
            continue
        detector_cls = _DETECTOR_MAP.get(key)
        if detector_cls is None:
            raise ValueError(
                f"unknown detector '{item}'. Available detectors: "
                f"{_AVAILABLE_DETECTOR_NAMES}"
            )
        active_detectors.append(detector_cls())

    return active_detectors


def _read_input(input_arg: str) -> str:
    """Safely read UTF-8 text from stdin or a specified file path.

    Raises privacy-safe exceptions without echoing source contents.
    """
    if input_arg == "-":
        if hasattr(sys.stdin, "buffer"):
            raw_bytes = sys.stdin.buffer.read()
            try:
                return raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("input from stdin is not valid UTF-8 text") from exc
        return sys.stdin.read()

    path = Path(input_arg)
    if not path.exists():
        raise FileNotFoundError(f"input file not found: '{input_arg}'")
    if path.is_dir():
        raise IsADirectoryError(f"input path is a directory: '{input_arg}'")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input file '{input_arg}' is not valid UTF-8 text") from exc
    except OSError as exc:
        raise OSError(
            f"cannot read input file '{input_arg}': {exc.strerror or exc}"
        ) from exc


def _write_output(
    output_arg: str,
    content: str,
    input_arg: str | None = None,
) -> None:
    """Safely write UTF-8 text to stdout or a specified file path.

    Rejects unsafe overwrites where input and output refer to the same file.
    """
    if input_arg is not None and input_arg != "-" and output_arg != "-":
        try:
            in_path = Path(input_arg).resolve()
            out_path = Path(output_arg).resolve()
            if in_path == out_path or (
                in_path.exists()
                and out_path.exists()
                and os.path.samefile(in_path, out_path)
            ):
                raise ValueError(
                    f"input and output cannot refer to the same file: '{input_arg}'"
                )
        except (FileNotFoundError, OSError):
            pass

    if output_arg == "-":
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(content.encode("utf-8"))
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(content)
            sys.stdout.flush()
        return

    out_path = Path(output_arg)
    try:
        out_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise OSError(
            f"cannot write output file '{output_arg}': {exc.strerror or exc}"
        ) from exc


def _cmd_detect(args: argparse.Namespace) -> int:
    """Handle 'detect' subcommand."""
    text = _read_input(args.input)
    detectors = _parse_detectors(args.detectors)
    detections = detect(text, detectors=detectors)

    # Output machine-readable JSON without sensitive values, spans, or text
    data = [
        {
            "type": d.type,
            "start": d.start,
            "end": d.end,
        }
        for d in detections
    ]
    json_output = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _write_output(args.output, json_output, input_arg=args.input)
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """Handle 'report' subcommand."""
    text = _read_input(args.input)
    detectors = _parse_detectors(args.detectors)
    report = detection_report(text, detectors=detectors)

    report_dict = {
        "total_detections": report.total_detections,
        "counts": dict(report.counts),
        "distinct_types": report.distinct_types,
        "has_conflicts": report.has_conflicts,
        "conflict_pairs": report.conflict_pairs,
        "conflicting_detections": report.conflicting_detections,
        "duplicate_groups": report.duplicate_groups,
    }
    json_output = json.dumps(report_dict, indent=2, ensure_ascii=False) + "\n"
    _write_output(args.output, json_output, input_arg=args.input)
    return 0


def _cmd_redact(args: argparse.Namespace) -> int:
    """Handle 'redact' subcommand."""
    conflict_policy: ConflictPolicy = args.conflict_policy
    type_priority: list[str] | None = None

    if conflict_policy == "priority":
        if not args.priority:
            raise ValueError(
                "--priority is required when --conflict-policy is 'priority'"
            )
        raw_types = [t.strip() for t in args.priority.split(",")]
        type_priority = [t for t in raw_types if t]
        if not type_priority:
            raise ValueError("--priority must contain at least one entity type name")
    else:
        if args.priority:
            raise ValueError(
                "--priority can only be used when --conflict-policy is 'priority'"
            )

    text = _read_input(args.input)
    detectors = _parse_detectors(args.detectors)
    redacted_text = redact(
        text,
        detectors=detectors,
        conflict_policy=conflict_policy,
        type_priority=type_priority,
    )
    _write_output(args.output, redacted_text, input_arg=args.input)
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Build and configure the top-level argparse ArgumentParser."""
    parser = argparse.ArgumentParser(
        prog="fa-redact",
        description=(
            "Privacy-first Persian/Iranian Personally Identifiable Information (PII) "
            "detection, redaction, and reporting toolkit."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )

    subparsers = parser.add_subparsers(
        title="subcommands",
        dest="subcommand",
        required=True,
        metavar="<command>",
    )

    # 1. detect subcommand
    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect PII entities and output structural detection metadata as JSON.",
        description=(
            "Detect PII entities in input text and output structural metadata (type, "
            "start, end) as JSON without exposing raw or normalized identifier values."
        ),
    )
    detect_parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input text file path or '-' to read from stdin (default: '-').",
    )
    detect_parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file path or '-' for stdout (default: '-').",
    )
    detect_parser.add_argument(
        "-d",
        "--detectors",
        default=None,
        help=(
            "Comma-separated list of detectors to run "
            "(e.g. 'national_id,mobile,iban'). Replaces default detectors."
        ),
    )
    detect_parser.set_defaults(func=_cmd_detect)

    # 2. report subcommand
    report_parser = subparsers.add_parser(
        "report",
        help="Generate a privacy-safe aggregate detection summary as JSON.",
        description=(
            "Generate a privacy-safe, value-free aggregate detection summary "
            "containing counts and conflict indicators as JSON."
        ),
    )
    report_parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input text file path or '-' to read from stdin (default: '-').",
    )
    report_parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file path or '-' for stdout (default: '-').",
    )
    report_parser.add_argument(
        "-d",
        "--detectors",
        default=None,
        help=(
            "Comma-separated list of detectors to run "
            "(e.g. 'national_id,mobile,iban'). Replaces default detectors."
        ),
    )
    report_parser.set_defaults(func=_cmd_report)

    # 3. redact subcommand
    redact_parser = subparsers.add_parser(
        "redact",
        help="Redact detected PII entities with typed placeholders.",
        description=(
            "Redact detected PII entities in input text by replacing them with "
            "deterministic typed placeholders (e.g. [IR_NATIONAL_ID_1])."
        ),
    )
    redact_parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input text file path or '-' to read from stdin (default: '-').",
    )
    redact_parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Output file path or '-' for stdout (default: '-').",
    )
    redact_parser.add_argument(
        "-d",
        "--detectors",
        default=None,
        help=(
            "Comma-separated list of detectors to run "
            "(e.g. 'national_id,mobile,iban'). Replaces default detectors."
        ),
    )
    redact_parser.add_argument(
        "-c",
        "--conflict-policy",
        choices=["reject", "longest", "priority"],
        default="reject",
        help="Conflict policy for overlaps: 'reject', 'longest', or 'priority'.",
    )
    redact_parser.add_argument(
        "-p",
        "--priority",
        default=None,
        help=(
            "Comma-separated list of entity types in descending priority order "
            "(required when --conflict-policy is 'priority', e.g. 'BANK_CARD,EMAIL')."
        ),
    )
    redact_parser.set_defaults(func=_cmd_redact)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for fa-redact."""
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
        return int(args.func(args))
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except (
        ValueError,
        TypeError,
        FileNotFoundError,
        IsADirectoryError,
        OSError,
    ) as exc:
        sys.stderr.write(f"fa-redact: error: {exc}\n")
        return 1
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(
            f"fa-redact: error: unexpected failure: {type(exc).__name__}\n"
        )
        return 1
