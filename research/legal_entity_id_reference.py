"""Research reference for candidate Legal Entity National ID checksum algorithms.

RESEARCH REFERENCE IMPLEMENTATION ONLY.
NOT PUBLIC RUNTIME API. DO NOT EXPORT FROM fa_redact.

This module provides reference implementations of candidate checksum formulas
identified during Phase 27 research for Iranian Legal Entity National ID
(شناسه ملی اشخاص حقوقی). It allows deterministic offline comparison and
property verification across candidate algorithm variants.
"""

from __future__ import annotations

from typing import Final

# Candidate coefficients used in Variant A and Variant B
_COEFFICIENTS_VARIANT_A: Final[tuple[int, ...]] = (
    29,
    27,
    23,
    19,
    17,
    29,
    27,
    23,
    19,
    17,
)

_COEFFICIENTS_VARIANT_C: Final[tuple[int, ...]] = (
    11,
    10,
    9,
    8,
    7,
    6,
    5,
    4,
    3,
    2,
)


def compute_legal_entity_checksum_variant_a(digits_10: str) -> int:
    """Compute check digit using Variant A (consensus prime weights).

    Formula:
        add = d[9] + 2
        total = sum((d[i] + add) * coef[i] for i in range(10))
        rem = total % 11
        check_digit = 0 if rem == 10 else rem

    Args:
        digits_10: Exactly 10 ASCII numeric digits.

    Returns:
        Integer check digit (0-9).
    """
    if len(digits_10) != 10 or not digits_10.isdigit():
        raise ValueError("Input must be exactly 10 ASCII digits")

    d = [int(c) for c in digits_10]
    add_val = d[9] + 2
    total = sum((d[i] + add_val) * _COEFFICIENTS_VARIANT_A[i] for i in range(10))
    rem = total % 11
    return 0 if rem == 10 else rem


def verify_legal_entity_id_variant_a(candidate: str) -> bool:
    """Verify an 11-digit legal entity national ID using Variant A."""
    if len(candidate) != 11 or not candidate.isdigit():
        return False
    # Reject repeated-digit pseudo-values
    if len(set(candidate)) == 1:
        return False
    expected = compute_legal_entity_checksum_variant_a(candidate[:10])
    return int(candidate[10]) == expected


def compute_legal_entity_checksum_variant_b(digits_10: str) -> int:
    """Compute check digit using Variant B (constant +2 offset with prime weights).

    Formula:
        total = sum((d[i] + 2) * coef[i] for i in range(10))
        rem = total % 11
        check_digit = 0 if rem == 10 else rem

    Args:
        digits_10: Exactly 10 ASCII numeric digits.

    Returns:
        Integer check digit (0-9).
    """
    if len(digits_10) != 10 or not digits_10.isdigit():
        raise ValueError("Input must be exactly 10 ASCII digits")

    d = [int(c) for c in digits_10]
    total = sum((d[i] + 2) * _COEFFICIENTS_VARIANT_A[i] for i in range(10))
    rem = total % 11
    return 0 if rem == 10 else rem


def verify_legal_entity_id_variant_b(candidate: str) -> bool:
    """Verify an 11-digit legal entity national ID using Variant B."""
    if len(candidate) != 11 or not candidate.isdigit():
        return False
    if len(set(candidate)) == 1:
        return False
    expected = compute_legal_entity_checksum_variant_b(candidate[:10])
    return int(candidate[10]) == expected


def compute_legal_entity_checksum_variant_c(digits_10: str) -> int:
    """Compute check digit using Variant C (linear descending weights 11..2).

    Formula:
        total = sum(d[i] * (11 - i) for i in range(10))
        rem = total % 11
        check_digit = rem if rem < 2 else 11 - rem

    Args:
        digits_10: Exactly 10 ASCII numeric digits.

    Returns:
        Integer check digit (0-9).
    """
    if len(digits_10) != 10 or not digits_10.isdigit():
        raise ValueError("Input must be exactly 10 ASCII digits")

    d = [int(c) for c in digits_10]
    total = sum(d[i] * _COEFFICIENTS_VARIANT_C[i] for i in range(10))
    rem = total % 11
    return rem if rem < 2 else 11 - rem


def verify_legal_entity_id_variant_c(candidate: str) -> bool:
    """Verify an 11-digit legal entity national ID using Variant C."""
    if len(candidate) != 11 or not candidate.isdigit():
        return False
    if len(set(candidate)) == 1:
        return False
    expected = compute_legal_entity_checksum_variant_c(candidate[:10])
    return int(candidate[10]) == expected


def compute_legal_entity_checksum_variant_d(digits_10: str) -> int:
    """Compute check digit using Variant D (unadjusted prime weights modulo 11).

    Formula:
        total = sum(d[i] * coef[i] for i in range(10))
        rem = total % 11
        check_digit = 0 if rem == 10 else rem

    Args:
        digits_10: Exactly 10 ASCII numeric digits.

    Returns:
        Integer check digit (0-9).
    """
    if len(digits_10) != 10 or not digits_10.isdigit():
        raise ValueError("Input must be exactly 10 ASCII digits")

    d = [int(c) for c in digits_10]
    total = sum(d[i] * _COEFFICIENTS_VARIANT_A[i] for i in range(10))
    rem = total % 11
    return 0 if rem == 10 else rem


def verify_legal_entity_id_variant_d(candidate: str) -> bool:
    """Verify an 11-digit legal entity national ID using Variant D."""
    if len(candidate) != 11 or not candidate.isdigit():
        return False
    if len(set(candidate)) == 1:
        return False
    expected = compute_legal_entity_checksum_variant_d(candidate[:10])
    return int(candidate[10]) == expected


def compare_checksum_variants(
    sample_prefixes: list[str],
) -> dict[str, dict[str, int]]:
    """Compare check digits generated by all candidate variants across inputs.

    Args:
        sample_prefixes: List of 10-digit numeric strings.

    Returns:
        Mapping of prefix to dictionary of variant name to computed check digit.
    """
    results: dict[str, dict[str, int]] = {}
    for prefix in sample_prefixes:
        results[prefix] = {
            "variant_a": compute_legal_entity_checksum_variant_a(prefix),
            "variant_b": compute_legal_entity_checksum_variant_b(prefix),
            "variant_c": compute_legal_entity_checksum_variant_c(prefix),
            "variant_d": compute_legal_entity_checksum_variant_d(prefix),
        }
    return results
