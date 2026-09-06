"""Comprehensive tests for explicit detection conflict resolution (Phase 16)."""

import pytest

from fa_redact import Detection, resolve_detection_conflicts


def _make_detection(
    type_: str,
    start: int,
    end: int,
    raw_char: str = "x",
    norm_char: str = "x",
) -> Detection:
    """Helper to create synthetic Detection instances for conflict tests."""
    length = end - start
    return Detection(
        type=type_,
        start=start,
        end=end,
        value=raw_char * length,
        normalized_value=norm_char * length,
    )


class TestConflictResolutionValidation:
    """Unit tests for input validation and policy configuration."""

    def test_empty_sequence_returns_empty_list(self) -> None:
        """Verify empty input returns empty list across all policies."""
        assert resolve_detection_conflicts([], policy="reject") == []
        assert resolve_detection_conflicts([], policy="longest") == []
        assert (
            resolve_detection_conflicts(
                [], policy="priority", type_priority=["EMAIL", "IR_MOBILE"]
            )
            == []
        )

    def test_invalid_detections_type_raises_type_error(self) -> None:
        """Verify non-sequence, str, and bytes input raise TypeError."""
        with pytest.raises(TypeError, match=r"detections must be a Sequence"):
            resolve_detection_conflicts("not a sequence")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match=r"detections must be a Sequence"):
            resolve_detection_conflicts(b"bytes")  # type: ignore[arg-type]
        with pytest.raises(TypeError, match=r"detections must be a Sequence"):
            resolve_detection_conflicts(123)  # type: ignore[arg-type]

    def test_non_detection_item_raises_type_error(self) -> None:
        """Verify items that are not Detection instances raise TypeError."""
        with pytest.raises(TypeError, match=r"Item at index 1 is not a Detection"):
            resolve_detection_conflicts(
                [_make_detection("EMAIL", 0, 5), "invalid_item"]  # type: ignore[list-item]
            )

    def test_invalid_policy_raises_value_error(self) -> None:
        """Verify unsupported policy string raises ValueError."""
        with pytest.raises(ValueError, match=r"Invalid conflict policy 'unknown'"):
            resolve_detection_conflicts([], policy="unknown")  # type: ignore[arg-type]

    def test_type_priority_with_reject_raises_value_error(self) -> None:
        """Verify supplying type_priority with policy='reject' raises ValueError."""
        with pytest.raises(
            ValueError, match=r"type_priority is only valid when policy='priority'"
        ):
            resolve_detection_conflicts(
                [], policy="reject", type_priority=["EMAIL", "BANK_CARD"]
            )

    def test_type_priority_with_longest_raises_value_error(self) -> None:
        """Verify supplying type_priority with policy='longest' raises ValueError."""
        with pytest.raises(
            ValueError, match=r"type_priority is only valid when policy='priority'"
        ):
            resolve_detection_conflicts(
                [], policy="longest", type_priority=["EMAIL", "BANK_CARD"]
            )

    def test_priority_without_type_priority_raises_value_error(self) -> None:
        """Verify policy='priority' without type_priority raises ValueError."""
        with pytest.raises(
            ValueError, match=r"type_priority must be provided when policy='priority'"
        ):
            resolve_detection_conflicts([], policy="priority", type_priority=None)

    def test_type_priority_not_sequence_raises_type_error(self) -> None:
        """Verify type_priority as str, bytes, or int raises TypeError."""
        with pytest.raises(TypeError, match=r"type_priority must be a Sequence"):
            resolve_detection_conflicts(
                [],
                policy="priority",
                type_priority="EMAIL",
            )
        with pytest.raises(TypeError, match=r"type_priority must be a Sequence"):
            resolve_detection_conflicts(
                [],
                policy="priority",
                type_priority=b"EMAIL",  # type: ignore[arg-type]
            )
        with pytest.raises(TypeError, match=r"type_priority must be a Sequence"):
            resolve_detection_conflicts(
                [],
                policy="priority",
                type_priority=123,  # type: ignore[arg-type]
            )

    def test_type_priority_empty_sequence_raises_value_error(self) -> None:
        """Verify empty type_priority sequence raises ValueError."""
        with pytest.raises(
            ValueError, match=r"type_priority must be a non-empty sequence"
        ):
            resolve_detection_conflicts([], policy="priority", type_priority=[])

    def test_type_priority_non_string_element_raises_type_error(self) -> None:
        """Verify non-string element in type_priority raises TypeError."""
        with pytest.raises(TypeError, match=r"Item at index 1 .* is not a string"):
            resolve_detection_conflicts(
                [],
                policy="priority",
                type_priority=["EMAIL", 123],  # type: ignore[list-item]
            )

    def test_type_priority_empty_string_element_raises_value_error(self) -> None:
        """Verify empty string element in type_priority raises ValueError."""
        with pytest.raises(ValueError, match=r"Item at index 1 .* is an empty string"):
            resolve_detection_conflicts(
                [], policy="priority", type_priority=["EMAIL", ""]
            )

    def test_type_priority_duplicate_element_raises_value_error(self) -> None:
        """Verify duplicate type names in type_priority raise ValueError."""
        with pytest.raises(
            ValueError, match=r"Duplicate entity type 'EMAIL' in type_priority"
        ):
            resolve_detection_conflicts(
                [], policy="priority", type_priority=["EMAIL", "BANK_CARD", "EMAIL"]
            )

    def test_caller_list_mutation_isolation(self) -> None:
        """Verify mutating caller's detections list does not affect returned list."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("IR_MOBILE", 20, 30)
        caller_list = [d2, d1]
        resolved = resolve_detection_conflicts(caller_list, policy="reject")

        # Mutate caller list
        caller_list.clear()

        assert len(resolved) == 2
        assert resolved[0] == d1
        assert resolved[1] == d2


class TestRejectPolicy:
    """Unit tests for default 'reject' policy."""

    def test_single_detection(self) -> None:
        """Verify single detection is returned in a list."""
        d = _make_detection("EMAIL", 5, 15)
        res = resolve_detection_conflicts([d], policy="reject")
        assert res == [d]

    def test_multiple_non_conflicting_sorted(self) -> None:
        """Verify non-conflicting detections are returned sorted deterministically."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("BANK_CARD", 15, 31)
        d3 = _make_detection("IR_MOBILE", 40, 51)
        # Pass in unsorted order
        res = resolve_detection_conflicts([d3, d1, d2], policy="reject")
        assert res == [d1, d2, d3]

    def test_adjacent_spans_do_not_conflict(self) -> None:
        """Verify adjacent spans [0, 5) and [5, 10) do not conflict."""
        d1 = _make_detection("TYPE_A", 0, 5)
        d2 = _make_detection("TYPE_B", 5, 10)
        res = resolve_detection_conflicts([d2, d1], policy="reject")
        assert res == [d1, d2]

    def test_partial_overlap_raises_value_error(self) -> None:
        """Verify partial overlap raises ValueError with privacy-safe message."""
        d1 = _make_detection("TYPE_A", 0, 10)
        d2 = _make_detection("TYPE_B", 8, 15)
        with pytest.raises(
            ValueError,
            match=(
                r"Overlapping detections at spans \[0:10\] \(TYPE_A\) and "
                r"\[8:15\] \(TYPE_B\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="reject")

    def test_nested_overlap_raises_value_error(self) -> None:
        """Verify nested overlap raises ValueError."""
        d1 = _make_detection("OUTER", 0, 20)
        d2 = _make_detection("INNER", 5, 10)
        with pytest.raises(
            ValueError,
            match=(
                r"Overlapping detections at spans \[0:20\] \(OUTER\) and "
                r"\[5:10\] \(INNER\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="reject")

    def test_exact_duplicate_raises_value_error(self) -> None:
        """Verify exact duplicate detections raise ValueError under reject."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("EMAIL", 0, 10)
        with pytest.raises(
            ValueError,
            match=(
                r"Overlapping detections at spans \[0:10\] \(EMAIL\) and "
                r"\[0:10\] \(EMAIL\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="reject")

    def test_same_span_different_type_raises_value_error(self) -> None:
        """Verify same span with different types raises ValueError under reject."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("CUSTOM_ID", 0, 10)
        with pytest.raises(
            ValueError,
            match=(
                r"Overlapping detections at spans \[0:10\] \(CUSTOM_ID\) and "
                r"\[0:10\] \(EMAIL\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="reject")

    def test_error_message_does_not_contain_raw_or_normalized_values(self) -> None:
        """Verify error message never leaks raw or normalized PII values."""
        d1 = Detection(
            type="EMAIL",
            start=0,
            end=16,
            value="secret1@test.com",
            normalized_value="secret1@test.com",
        )
        d2 = Detection(
            type="BANK_CARD",
            start=0,
            end=16,
            value="6037991122334455",
            normalized_value="6037991122334455",
        )
        with pytest.raises(ValueError) as exc_info:
            resolve_detection_conflicts([d1, d2], policy="reject")

        msg = str(exc_info.value)
        assert "secret1@test.com" not in msg
        assert "6037991122334455" not in msg
        assert "[0:16] (BANK_CARD)" in msg
        assert "[0:16] (EMAIL)" in msg


class TestLongestPolicy:
    """Unit tests for greedy 'longest' conflict resolution policy."""

    def test_longer_span_beats_shorter_span(self) -> None:
        """Verify strictly longer overlapping span is selected."""
        d_long = _make_detection("EMAIL", 0, 30)
        d_short = _make_detection("BANK_CARD", 0, 16)
        res = resolve_detection_conflicts([d_short, d_long], policy="longest")
        assert res == [d_long]

    def test_nested_longer_wins(self) -> None:
        """Verify outer longer span wins over inner shorter span."""
        d_outer = _make_detection("OUTER", 0, 20)
        d_inner = _make_detection("INNER", 5, 10)
        res = resolve_detection_conflicts([d_inner, d_outer], policy="longest")
        assert res == [d_outer]

    def test_exact_duplicate_collapses(self) -> None:
        """Verify exact duplicate detections collapse into a single item."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("EMAIL", 0, 10)
        res = resolve_detection_conflicts([d1, d2], policy="longest")
        assert res == [d1]

    def test_equal_length_same_span_different_type_raises_value_error(self) -> None:
        """Verify equal-length spans with different types raise ValueError."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("CUSTOM_ID", 0, 10)
        with pytest.raises(
            ValueError,
            match=(
                r"Ambiguous conflict between equal-length detections at spans "
                r"\[0:10\] \(CUSTOM_ID\) and \[0:10\] \(EMAIL\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="longest")

    def test_equal_length_shifted_overlap_raises_value_error(self) -> None:
        """Verify equal-length shifted overlapping spans raise ValueError."""
        d1 = _make_detection("TYPE_A", 0, 10)
        d2 = _make_detection("TYPE_B", 2, 12)
        with pytest.raises(
            ValueError,
            match=(
                r"Ambiguous conflict between equal-length detections at spans "
                r"\[0:10\] \(TYPE_A\) and \[2:12\] \(TYPE_B\)"
            ),
        ):
            resolve_detection_conflicts([d1, d2], policy="longest")

    def test_equal_length_non_overlapping_survive(self) -> None:
        """Verify equal-length non-overlapping independent spans both survive."""
        d1 = _make_detection("TYPE_A", 0, 10)
        d2 = _make_detection("TYPE_B", 15, 25)
        res = resolve_detection_conflicts([d2, d1], policy="longest")
        assert res == [d1, d2]

    def test_adjacent_spans_survive(self) -> None:
        """Verify adjacent spans survive under longest policy."""
        d1 = _make_detection("TYPE_A", 0, 5)
        d2 = _make_detection("TYPE_B", 5, 10)
        res = resolve_detection_conflicts([d2, d1], policy="longest")
        assert res == [d1, d2]

    def test_transitive_conflict_longer_eliminates_multiple(self) -> None:
        """Verify a single long detection eliminates all overlapping candidates."""
        d_main = _make_detection("MAIN", 0, 20)  # len 20
        d_sub1 = _make_detection("SUB1", 2, 8)  # len 6
        d_sub2 = _make_detection("SUB2", 10, 18)  # len 8
        d_sub3 = _make_detection("SUB3", 15, 25)  # len 10
        res = resolve_detection_conflicts(
            [d_sub1, d_sub3, d_main, d_sub2], policy="longest"
        )
        assert res == [d_main]

    def test_transitive_conflict_chain_resolution(self) -> None:
        """Verify greedy elimination allows non-overlapping winner to survive."""
        d_a = _make_detection("A", 0, 20)  # len 20
        d_b = _make_detection("B", 15, 25)  # len 10, conflicts with A and C
        d_c = _make_detection("C", 24, 35)  # len 11, conflicts with B but not A
        res = resolve_detection_conflicts([d_b, d_c, d_a], policy="longest")
        # A (len 20) is accepted, B is discarded, C (len 11) is accepted
        assert res == [d_a, d_c]

    def test_transitive_conflict_chain_equal_length_ambiguity(self) -> None:
        """Verify overlapping equal-length active candidates raise ValueError."""
        d_a = _make_detection("A", 0, 10)  # len 10
        d_b = _make_detection("B", 8, 20)  # len 12
        d_c = _make_detection("C", 18, 30)  # len 12, overlaps with B on [18:20]
        with pytest.raises(
            ValueError,
            match=r"Ambiguous conflict between equal-length detections",
        ):
            resolve_detection_conflicts([d_a, d_b, d_c], policy="longest")


class TestPriorityPolicy:
    """Unit tests for explicit 'priority' conflict resolution policy."""

    def test_priority_beats_span_length(self) -> None:
        """Verify higher priority entity type wins over longer span."""
        d_email = _make_detection("EMAIL", 0, 30)  # len 30
        d_card = _make_detection("BANK_CARD", 0, 16)  # len 16

        # BANK_CARD has higher priority
        res = resolve_detection_conflicts(
            [d_email, d_card],
            policy="priority",
            type_priority=["BANK_CARD", "EMAIL"],
        )
        assert res == [d_card]

        # EMAIL has higher priority
        res2 = resolve_detection_conflicts(
            [d_card, d_email],
            policy="priority",
            type_priority=["EMAIL", "BANK_CARD"],
        )
        assert res2 == [d_email]

    def test_same_type_conflict_longer_span_wins(self) -> None:
        """Verify same-type conflict chooses longer span as secondary rule."""
        d_short = _make_detection("CUSTOM_ID", 2, 8)
        d_long = _make_detection("CUSTOM_ID", 0, 15)
        res = resolve_detection_conflicts(
            [d_short, d_long],
            policy="priority",
            type_priority=["CUSTOM_ID"],
        )
        assert res == [d_long]

    def test_same_type_exact_duplicate_collapses(self) -> None:
        """Verify same-type exact duplicate collapses into single detection."""
        d1 = _make_detection("CUSTOM_ID", 0, 10)
        d2 = _make_detection("CUSTOM_ID", 0, 10)
        res = resolve_detection_conflicts(
            [d1, d2],
            policy="priority",
            type_priority=["CUSTOM_ID"],
        )
        assert res == [d1]

    def test_same_type_equal_length_shifted_overlap_raises_value_error(self) -> None:
        """Verify same-type equal-length overlapping spans raise ValueError."""
        d1 = _make_detection("CUSTOM_ID", 0, 10)
        d2 = _make_detection("CUSTOM_ID", 5, 15)
        with pytest.raises(
            ValueError,
            match=(
                r"Ambiguous conflict between equal-priority detections at spans "
                r"\[0:10\] \(CUSTOM_ID\) and \[5:15\] \(CUSTOM_ID\)"
            ),
        ):
            resolve_detection_conflicts(
                [d1, d2],
                policy="priority",
                type_priority=["CUSTOM_ID"],
            )

    def test_different_types_same_span_resolved_by_priority(self) -> None:
        """Verify different types with exact same span are resolved by priority."""
        d1 = _make_detection("EMAIL", 0, 10)
        d2 = _make_detection("CUSTOM_ID", 0, 10)
        res = resolve_detection_conflicts(
            [d2, d1],
            policy="priority",
            type_priority=["CUSTOM_ID", "EMAIL"],
        )
        assert res == [d2]

    def test_conflicting_unlisted_type_raises_value_error(self) -> None:
        """Verify conflicting detection without configured priority raises error."""
        d_email = _make_detection("EMAIL", 0, 20)
        d_custom = _make_detection("CUSTOM_ID", 5, 15)
        with pytest.raises(
            ValueError,
            match=(
                r"Conflicting detection of type 'CUSTOM_ID' at span \[5:15\] "
                r"has no configured priority in type_priority"
            ),
        ):
            resolve_detection_conflicts(
                [d_email, d_custom],
                policy="priority",
                type_priority=["EMAIL"],  # CUSTOM_ID missing
            )

    def test_non_conflicting_unlisted_type_is_allowed_and_survives(self) -> None:
        """Verify non-conflicting detection of unlisted type survives untouched."""
        d_email = _make_detection("EMAIL", 0, 20)
        d_card = _make_detection("BANK_CARD", 0, 16)
        d_national_id = _make_detection("IR_NATIONAL_ID", 50, 60)

        # IR_NATIONAL_ID has no conflicts, so it is not required in type_priority
        res = resolve_detection_conflicts(
            [d_national_id, d_email, d_card],
            policy="priority",
            type_priority=["EMAIL", "BANK_CARD"],
        )
        assert res == [d_email, d_national_id]

    def test_adjacent_spans_survive_under_priority(self) -> None:
        """Verify adjacent spans survive without conflict under priority policy."""
        d1 = _make_detection("TYPE_A", 0, 5)
        d2 = _make_detection("TYPE_B", 5, 10)
        res = resolve_detection_conflicts(
            [d2, d1],
            policy="priority",
            type_priority=["TYPE_A", "TYPE_B"],
        )
        assert res == [d1, d2]

    def test_transitive_priority_elimination(self) -> None:
        """Verify priority elimination in connected conflict chain."""
        d_card = _make_detection("BANK_CARD", 0, 16)
        d_email = _make_detection("EMAIL", 0, 30)
        d_mobile = _make_detection("IR_MOBILE", 25, 36)

        # BANK_CARD eliminates EMAIL, allowing IR_MOBILE to survive
        res = resolve_detection_conflicts(
            [d_email, d_mobile, d_card],
            policy="priority",
            type_priority=["BANK_CARD", "EMAIL", "IR_MOBILE"],
        )
        assert res == [d_card, d_mobile]
