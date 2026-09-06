"""Comprehensive test suite for fa-redact CLI."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import fa_redact
from fa_redact.cli import _parse_detectors, create_parser, main
from fa_redact.detectors import (
    BankCardDetector,
    EmailDetector,
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
)

# ============================================================================
# Helper Fixtures & Utilities
# ============================================================================


def run_cli_args(
    argv: list[str],
    stdin_text: str | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> tuple[int, str, str]:
    """Run CLI main with given arguments and optional stdin."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()

    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    try:
        if stdin_text is not None:
            sys.stdin = io.StringIO(stdin_text)
        sys.stdout = out_buf
        sys.stderr = err_buf
        code = main(argv)
        return code, out_buf.getvalue(), err_buf.getvalue()
    finally:
        sys.stdin = orig_stdin
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr


# ============================================================================
# Unit Tests: Parser, Help, Version, and Detector Parsing
# ============================================================================


def test_cli_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """--version / -V prints program name and version and exits 0."""
    code = main(["--version"])
    assert code == 0
    out = capsys.readouterr().out
    assert f"fa-redact {fa_redact.__version__}" in out

    code = main(["-V"])
    assert code == 0
    out = capsys.readouterr().out
    assert f"fa-redact {fa_redact.__version__}" in out


def test_cli_help_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """--help / -h prints usage help and exits 0."""
    code = main(["--help"])
    assert code == 0
    out = capsys.readouterr().out
    assert "usage: fa-redact" in out
    assert "detect" in out
    assert "redact" in out
    assert "report" in out


def test_cli_no_subcommand_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    """Running fa-redact with no subcommand results in an exit code of 2."""
    code = main([])
    assert code == 2
    err = capsys.readouterr().err
    assert "usage: fa-redact" in err or "error" in err


def test_subcommand_help_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """Each subcommand provides a dedicated --help message."""
    for subcmd in ["detect", "redact", "report"]:
        code = main([subcmd, "--help"])
        assert code == 0
        out = capsys.readouterr().out
        assert f"usage: fa-redact {subcmd}" in out


def test_parse_detectors_default_is_none() -> None:
    """_parse_detectors(None) returns None to preserve library default detector set."""
    assert _parse_detectors(None) is None


def test_parse_detectors_empty_or_none_string() -> None:
    """Passing empty string or 'none' returns empty detector list."""
    assert _parse_detectors("") == []
    assert _parse_detectors("none") == []
    assert _parse_detectors("empty") == []


def test_parse_detectors_valid_names_and_aliases() -> None:
    """_parse_detectors resolves canonical names and synonyms."""
    detectors = _parse_detectors("national_id,mobile,iban,email,bank_card")
    assert detectors is not None
    assert len(detectors) == 5
    assert isinstance(detectors[0], IranianNationalIDDetector)
    assert isinstance(detectors[1], IranianMobileNumberDetector)
    assert isinstance(detectors[2], IranianIBANDetector)
    assert isinstance(detectors[3], EmailDetector)
    assert isinstance(detectors[4], BankCardDetector)

    # Test aliases
    alias_detectors = _parse_detectors("IR_NATIONAL_ID,ir_mobile,sheba,bank-card")
    assert alias_detectors is not None
    assert len(alias_detectors) == 4
    assert isinstance(alias_detectors[0], IranianNationalIDDetector)
    assert isinstance(alias_detectors[1], IranianMobileNumberDetector)
    assert isinstance(alias_detectors[2], IranianIBANDetector)
    assert isinstance(alias_detectors[3], BankCardDetector)


def test_parse_detectors_unknown_name_raises() -> None:
    """_parse_detectors raises ValueError on unknown detector names."""
    with pytest.raises(ValueError, match="unknown detector 'unknown_det'"):
        _parse_detectors("national_id,unknown_det")


# ============================================================================
# Functional Tests: Subcommand `detect`
# ============================================================================


def test_detect_stdin_to_stdout() -> None:
    """`detect` reads from stdin and outputs machine-readable JSON."""
    sample_text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹"
    code, stdout, stderr = run_cli_args(["detect"], stdin_text=sample_text)

    assert code == 0
    assert stderr == ""
    data: list[dict[str, Any]] = json.loads(stdout)
    assert len(data) == 2
    assert data[0]["type"] == "IR_NATIONAL_ID"
    assert data[0]["start"] == 7
    assert data[0]["end"] == 17
    assert data[1]["type"] == "IR_MOBILE"
    assert data[1]["start"] == 27
    assert data[1]["end"] == 38


def test_detect_from_file_to_file(tmp_path: Path) -> None:
    """`detect` reads from file and writes JSON to output file."""
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "detections.json"
    in_file.write_text("شبا IR641234567890123456789012 ثبت شد.", encoding="utf-8")

    code, stdout, stderr = run_cli_args(["detect", str(in_file), "-o", str(out_file)])
    assert code == 0
    assert stdout == ""
    assert stderr == ""

    out_content = out_file.read_text(encoding="utf-8")
    data = json.loads(out_content)
    assert len(data) == 1
    assert data[0]["type"] == "IR_IBAN"
    assert data[0]["start"] == 4
    assert data[0]["end"] == 30


def test_detect_privacy_invariants_no_values_or_text() -> None:
    """`detect` output JSON strictly excludes raw/normalized values and text."""
    secret_nid = "1234567891"
    sample_text = f"کد محرمانه: {secret_nid}"
    code, stdout, stderr = run_cli_args(["detect"], stdin_text=sample_text)

    assert code == 0
    assert secret_nid not in stdout
    assert "value" not in stdout
    assert "normalized_value" not in stdout
    assert "text" not in stdout
    assert "snippet" not in stdout
    assert "hash" not in stdout

    data = json.loads(stdout)
    assert len(data) == 1
    item = data[0]
    assert set(item.keys()) == {"type", "start", "end"}


def test_detect_empty_input_produces_empty_json_list() -> None:
    """`detect` on empty or clean text outputs `[]`."""
    code, stdout, stderr = run_cli_args(["detect"], stdin_text="متن بدون شناسه")
    assert code == 0
    data = json.loads(stdout)
    assert data == []


def test_detect_explicit_detectors_override_defaults() -> None:
    """Specifying --detectors replaces default detectors."""
    sample_text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و ایمیل test@example.com"

    # Default detector set ignores email
    code, stdout, _ = run_cli_args(["detect"], stdin_text=sample_text)
    assert code == 0
    data = json.loads(stdout)
    assert len(data) == 1
    assert data[0]["type"] == "IR_NATIONAL_ID"

    # Explicit --detectors email detects email and ignores national ID
    code, stdout, _ = run_cli_args(
        ["detect", "--detectors", "email"], stdin_text=sample_text
    )
    assert code == 0
    data = json.loads(stdout)
    assert len(data) == 1
    assert data[0]["type"] == "EMAIL"


# ============================================================================
# Functional Tests: Subcommand `report`
# ============================================================================


def test_report_stdin_to_stdout() -> None:
    """`report` reads from stdin and outputs aggregate DetectionReport JSON."""
    sample_text = (
        "کد ملی: ۱۲۳۴۵۶۷۸۹۱، همراه: ۰۹۱۲۳۴۵۶۷۸۹، شبا: IR641234567890123456789012"
    )
    code, stdout, stderr = run_cli_args(["report"], stdin_text=sample_text)

    assert code == 0
    assert stderr == ""
    data = json.loads(stdout)
    assert data["total_detections"] == 3
    assert data["distinct_types"] == 3
    assert data["counts"] == {
        "IR_IBAN": 1,
        "IR_MOBILE": 1,
        "IR_NATIONAL_ID": 1,
    }
    assert data["has_conflicts"] is False
    assert data["conflict_pairs"] == 0
    assert data["conflicting_detections"] == 0
    assert data["duplicate_groups"] == 0


def test_report_from_file_to_file(tmp_path: Path) -> None:
    """`report` reads from file and writes JSON to output file."""
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "report.json"
    in_file.write_text("تماس: ۰۹۱۲۳۴۵۶۷۸۹ و 09123456789", encoding="utf-8")

    code, stdout, stderr = run_cli_args(["report", str(in_file), "-o", str(out_file)])
    assert code == 0
    assert stdout == ""
    assert stderr == ""

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["total_detections"] == 2
    assert data["counts"] == {"IR_MOBILE": 2}
    assert data["distinct_types"] == 1
    assert data["has_conflicts"] is False


def test_report_privacy_invariants_no_values_or_spans() -> None:
    """`report` output JSON strictly contains only aggregate statistics."""
    sample_text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱"
    code, stdout, stderr = run_cli_args(["report"], stdin_text=sample_text)

    assert code == 0
    assert "۱۲۳۴۵۶۷۸۹۱" not in stdout
    assert "1234567891" not in stdout
    assert "value" not in stdout
    assert "normalized_value" not in stdout
    assert "start" not in stdout
    assert "end" not in stdout
    assert "span" not in stdout


def test_report_detects_conflicts() -> None:
    """`report` accurately surfaces conflicts across active detectors."""
    sample_text = "1234567890123452@example.com"
    code, stdout, _ = run_cli_args(
        ["report", "--detectors", "email,bank_card"],
        stdin_text=sample_text,
    )
    assert code == 0
    data = json.loads(stdout)
    assert data["total_detections"] == 2
    assert data["has_conflicts"] is True
    assert data["conflict_pairs"] == 1
    assert data["conflicting_detections"] == 2


# ============================================================================
# Functional Tests: Subcommand `redact`
# ============================================================================


def test_redact_stdin_to_stdout_default_detectors() -> None:
    """`redact` from stdin replaces default identifiers with placeholders."""
    sample_text = "کد ملی: ۱۲۳۴۵۶۷۸۹۱، تماس: ۰۹۱۲۳۴۵۶۷۸۹"
    code, stdout, stderr = run_cli_args(["redact"], stdin_text=sample_text)

    assert code == 0
    assert stderr == ""
    assert stdout == "کد ملی: [IR_NATIONAL_ID_1]، تماس: [IR_MOBILE_1]"


def test_redact_from_file_to_file(tmp_path: Path) -> None:
    """`redact` from input file writes redacted text to output file."""
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "redacted.txt"
    in_file.write_text("شبا: IR641234567890123456789012", encoding="utf-8")

    code, stdout, stderr = run_cli_args(["redact", str(in_file), "-o", str(out_file)])
    assert code == 0
    assert stdout == ""
    assert stderr == ""

    out_content = out_file.read_text(encoding="utf-8")
    assert out_content == "شبا: [IR_IBAN_1]"


def test_redact_conflict_policy_reject_by_default() -> None:
    """`redact` defaults to reject policy and fails on conflicting detections."""
    sample_text = "ایمیل: 1234567890123452@example.com"
    code, stdout, stderr = run_cli_args(
        ["redact", "--detectors", "email,bank_card"],
        stdin_text=sample_text,
    )
    assert code == 1
    assert stdout == ""
    assert "fa-redact: error:" in stderr
    assert "Overlapping detections" in stderr
    # Verify no PII value leaked in stderr
    assert "1234567890123452" not in stderr
    assert "example.com" not in stderr


def test_redact_conflict_policy_longest() -> None:
    """`redact` with --conflict-policy longest selects longest span."""
    sample_text = "ایمیل: 1234567890123452@example.com"
    code, stdout, stderr = run_cli_args(
        [
            "redact",
            "--detectors",
            "email,bank_card",
            "--conflict-policy",
            "longest",
        ],
        stdin_text=sample_text,
    )
    assert code == 0
    assert stderr == ""
    assert stdout == "ایمیل: [EMAIL_1]"


def test_redact_conflict_policy_priority() -> None:
    """`redact` with --conflict-policy priority resolves conflicts via --priority."""
    sample_text = "ایمیل: 1234567890123452@example.com"

    # Priority: BANK_CARD > EMAIL
    code, stdout, _ = run_cli_args(
        [
            "redact",
            "--detectors",
            "email,bank_card",
            "--conflict-policy",
            "priority",
            "--priority",
            "BANK_CARD,EMAIL",
        ],
        stdin_text=sample_text,
    )
    assert code == 0
    assert stdout == "ایمیل: [BANK_CARD_1]@example.com"

    # Priority: EMAIL > BANK_CARD
    code, stdout, _ = run_cli_args(
        [
            "redact",
            "--detectors",
            "email,bank_card",
            "--conflict-policy",
            "priority",
            "--priority",
            "EMAIL,BANK_CARD",
        ],
        stdin_text=sample_text,
    )
    assert code == 0
    assert stdout == "ایمیل: [EMAIL_1]"


def test_redact_priority_validation_errors() -> None:
    """Missing or inappropriate --priority arguments fail with clean errors."""
    # 1. priority policy without --priority
    code, _, stderr = run_cli_args(
        ["redact", "--conflict-policy", "priority"],
        stdin_text="test text",
    )
    assert code == 1
    assert "--priority is required when --conflict-policy is 'priority'" in stderr

    # 2. priority given with non-priority policy
    code, _, stderr = run_cli_args(
        [
            "redact",
            "--conflict-policy",
            "reject",
            "--priority",
            "BANK_CARD,EMAIL",
        ],
        stdin_text="test text",
    )
    assert code == 1
    assert "--priority can only be used when --conflict-policy is 'priority'" in stderr

    # 3. empty --priority value
    code, _, stderr = run_cli_args(
        [
            "redact",
            "--conflict-policy",
            "priority",
            "--priority",
            "  , , ",
        ],
        stdin_text="test text",
    )
    assert code == 1
    assert "--priority must contain at least one entity type name" in stderr


# ============================================================================
# Functional Tests: File & I/O Error Handling & Privacy
# ============================================================================


def test_nonexistent_input_file_error() -> None:
    """Nonexistent input file raises clean error with exit code 1."""
    code, stdout, stderr = run_cli_args(["detect", "nonexistent_file_12345.txt"])
    assert code == 1
    assert stdout == ""
    assert "fa-redact: error: input file not found:" in stderr


def test_input_is_directory_error(tmp_path: Path) -> None:
    """Passing directory as input raises clean error with exit code 1."""
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    code, stdout, stderr = run_cli_args(["detect", str(sub_dir)])
    assert code == 1
    assert stdout == ""
    assert "fa-redact: error: input path is a directory:" in stderr


def test_same_input_and_output_file_rejected(tmp_path: Path) -> None:
    """Input and output pointing to the same file path is rejected."""
    target_file = tmp_path / "data.txt"
    target_file.write_text("کد ملی ۱۲۳۴۵۶۷۸۹۱", encoding="utf-8")

    code, stdout, stderr = run_cli_args(
        ["redact", str(target_file), "-o", str(target_file)]
    )
    assert code == 1
    assert stdout == ""
    assert "input and output cannot refer to the same file" in stderr
    # Verify file content was not destroyed or truncated
    assert target_file.read_text(encoding="utf-8") == "کد ملی ۱۲۳۴۵۶۷۸۹۱"


def test_invalid_utf8_input_file(tmp_path: Path) -> None:
    """Non-UTF-8 input file is rejected with clean error without leaking bytes."""
    bad_file = tmp_path / "bad.bin"
    bad_file.write_bytes(b"\x80\x81\x82\xff\xfe")

    code, stdout, stderr = run_cli_args(["detect", str(bad_file)])
    assert code == 1
    assert stdout == ""
    assert "fa-redact: error:" in stderr
    assert "not valid UTF-8 text" in stderr


def test_unknown_detector_argument_error() -> None:
    """Passing unknown detector name produces error on stderr and exit code 1."""
    code, stdout, stderr = run_cli_args(
        ["detect", "--detectors", "invalid_detector_xyz"],
        stdin_text="test text",
    )
    assert code == 1
    assert stdout == ""
    assert "unknown detector 'invalid_detector_xyz'" in stderr
    assert "Available detectors:" in stderr


# ============================================================================
# Subprocess Tests: `python -m fa_redact` & Script Execution
# ============================================================================


def test_python_m_fa_redact_version() -> None:
    """`python -m fa_redact --version` runs via __main__.py."""
    res = subprocess.run(
        [sys.executable, "-m", "fa_redact", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert f"fa-redact {fa_redact.__version__}" in res.stdout


def test_python_m_fa_redact_redact_pipeline() -> None:
    """`python -m fa_redact redact` processes stdin and outputs to stdout."""
    res = subprocess.run(
        [sys.executable, "-m", "fa_redact", "redact"],
        input="شماره ۰۹۱۲۳۴۵۶۷۸۹",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 0
    assert res.stdout == "شماره [IR_MOBILE_1]"
    assert res.stderr == ""


def test_python_m_fa_redact_report_pipeline() -> None:
    """`python -m fa_redact report` outputs valid JSON report."""
    res = subprocess.run(
        [sys.executable, "-m", "fa_redact", "report"],
        input="کد ملی ۱۲۳۴۵۶۷۸۹۱",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["total_detections"] == 1
    assert data["counts"] == {"IR_NATIONAL_ID": 1}


# ============================================================================
# Additional Edge Case & Coverage Tests
# ============================================================================


def test_detectors_none_option_across_subcommands() -> None:
    """Passing --detectors none runs no detectors across all subcommands."""
    text = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹"

    # 1. detect
    code, stdout, _ = run_cli_args(["detect", "--detectors", "none"], stdin_text=text)
    assert code == 0
    assert json.loads(stdout) == []

    # 2. redact
    code, stdout, _ = run_cli_args(["redact", "--detectors", "none"], stdin_text=text)
    assert code == 0
    assert stdout == text

    # 3. report
    code, stdout, _ = run_cli_args(["report", "--detectors", "none"], stdin_text=text)
    assert code == 0
    data = json.loads(stdout)
    assert data["total_detections"] == 0
    assert data["counts"] == {}


def test_write_output_directory_error(tmp_path: Path) -> None:
    """Attempting to write output to a directory path raises clean error."""
    out_dir = tmp_path / "out_dir"
    out_dir.mkdir()
    code, stdout, stderr = run_cli_args(
        ["redact", "-o", str(out_dir)], stdin_text="متن تستی"
    )
    assert code == 1
    assert "fa-redact: error:" in stderr


def test_main_with_default_sys_argv(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Calling main() with no arguments parses sys.argv."""
    monkeypatch.setattr(sys, "argv", ["fa-redact", "--version"])
    code = main()
    assert code == 0
    out = capsys.readouterr().out
    assert f"fa-redact {fa_redact.__version__}" in out


def test_parser_construction() -> None:
    """Verify that create_parser builds the expected ArgumentParser hierarchy."""
    parser = create_parser()
    assert parser.prog == "fa-redact"
    assert parser.description is not None
    assert "PII" in parser.description
