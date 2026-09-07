"""Comprehensive tests for lazy batch-processing helpers."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from typing import Any

import pytest

import fa_redact
from fa_redact import (
    Detection,
    DetectionReport,
    EmailDetector,
    IranianIBANDetector,
    IranianMobileNumberDetector,
    IranianNationalIDDetector,
    detect,
    detect_many,
    detection_report,
    redact,
    redact_many,
    report_many,
)
from fa_redact.batch import (
    detect_many as sub_detect_many,
)
from fa_redact.batch import (
    redact_many as sub_redact_many,
)
from fa_redact.batch import (
    report_many as sub_report_many,
)
from fa_redact.protocols import Detector


class FakeCustomDetector:
    """Fake detector returning custom entity spans for testing."""

    def __init__(self, target_type: str = "TEST_PII") -> None:
        self.target_type = target_type
        self.call_count = 0

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        self.call_count += 1
        idx = normalized_text.find("CUSTOM_ENTITY")
        if idx != -1:
            return [
                Detection(
                    type=self.target_type,
                    value=original_text[idx : idx + 13],
                    normalized_value="CUSTOM_ENTITY",
                    start=idx,
                    end=idx + 13,
                )
            ]
        return []


class FakePersonDetector:
    """Fake PERSON detector implementing Detector protocol without ML dependencies."""

    def detect(
        self,
        original_text: str,
        normalized_text: str,
    ) -> Sequence[Detection]:
        idx = original_text.find("علی رضایی")
        if idx != -1:
            return [
                Detection(
                    type="PERSON",
                    value="علی رضایی",
                    normalized_value="علی رضایی",
                    start=idx,
                    end=idx + 9,
                )
            ]
        return []


# 1. detect_many returns iterator/lazy iterable
def test_detect_many_returns_iterator() -> None:
    res = detect_many(["کد ملی ۱۲۳۴۵۶۷۸۹۱"])
    assert isinstance(res, Iterator)
    assert iter(res) is res


# 2. redact_many returns iterator/lazy iterable
def test_redact_many_returns_iterator() -> None:
    res = redact_many(["کد ملی ۱۲۳۴۵۶۷۸۹۱"])
    assert isinstance(res, Iterator)
    assert iter(res) is res


# 3. report_many returns iterator/lazy iterable
def test_report_many_returns_iterator() -> None:
    res = report_many(["کد ملی ۱۲۳۴۵۶۷۸۹۱"])
    assert isinstance(res, Iterator)
    assert iter(res) is res


# 4. empty detect_many
def test_empty_detect_many() -> None:
    res = list(detect_many([]))
    assert res == []


# 5. empty redact_many
def test_empty_redact_many() -> None:
    res = list(redact_many([]))
    assert res == []


# 6. empty report_many
def test_empty_report_many() -> None:
    res = list(report_many([]))
    assert res == []


# 7. list input works
def test_list_input_works() -> None:
    docs = ["کد ملی ۱۲۳۴۵۶۷۸۹۱", "شماره ۰۹۱۲۳۴۵۶۷۸۹"]
    res = list(redact_many(docs))
    assert len(res) == 2
    assert "[IR_NATIONAL_ID_1]" in res[0]
    assert "[IR_MOBILE_1]" in res[1]


# 8. tuple input works
def test_tuple_input_works() -> None:
    docs = ("کد ملی ۱۲۳۴۵۶۷۸۹۱", "شماره ۰۹۱۲۳۴۵۶۷۸۹")
    res = list(detect_many(docs))
    assert len(res) == 2
    assert res[0][0].type == "IR_NATIONAL_ID"
    assert res[1][0].type == "IR_MOBILE"


# 9. generator input works
def test_generator_input_works() -> None:
    def gen_docs() -> Iterator[str]:
        yield "کد ملی ۱۲۳۴۵۶۷۸۹۱"
        yield "شماره ۰۹۱۲۳۴۵۶۷۸۹"

    res = list(report_many(gen_docs()))
    assert len(res) == 2
    assert res[0].total_detections == 1
    assert res[1].total_detections == 1


# 10. one-shot iterator consumed exactly once
def test_one_shot_iterator_consumed_once() -> None:
    consumed_count = 0

    def one_shot() -> Iterator[str]:
        nonlocal consumed_count
        for item in ["متن یک", "متن دو", "متن سه"]:
            consumed_count += 1
            yield item

    stream = one_shot()
    res = list(redact_many(stream))
    assert len(res) == 3
    assert consumed_count == 3
    # Verifying one-shot stream is exhausted and was not re-iterated
    assert list(stream) == []


# 11. direct str container rejected
def test_direct_str_container_rejected() -> None:
    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        detect_many("کد ملی ۱۲۳۴۵۶۷۸۹۱")

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        redact_many("کد ملی ۱۲۳۴۵۶۷۸۹۱")

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        report_many("کد ملی ۱۲۳۴۵۶۷۸۹۱")


# 12. bytes container rejected
def test_direct_bytes_container_rejected() -> None:
    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        detect_many(b"some bytes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        redact_many(b"some bytes")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        report_many(b"some bytes")  # type: ignore[arg-type]


# 13. bytearray container rejected
def test_direct_bytearray_container_rejected() -> None:
    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        detect_many(bytearray(b"some bytearray"))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        redact_many(bytearray(b"some bytearray"))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="texts must be an iterable of str documents"):
        report_many(bytearray(b"some bytearray"))  # type: ignore[arg-type]


# Non-iterable object rejected
def test_non_iterable_container_rejected() -> None:
    with pytest.raises(TypeError, match="texts must be an Iterable"):
        detect_many(12345)  # type: ignore[arg-type]


# 14. non-string item rejected at correct consumed index
def test_non_string_item_rejected_at_correct_index() -> None:
    items: list[Any] = ["سند معتبر اول", "سند معتبر دوم", 12345, "سند معتبر چهارم"]

    it_detect = detect_many(items)
    next(it_detect)
    next(it_detect)
    with pytest.raises(TypeError, match=r"item at index 2 must be a str, got int"):
        next(it_detect)

    it_redact = redact_many(items)
    next(it_redact)
    next(it_redact)
    with pytest.raises(TypeError, match=r"item at index 2 must be a str, got int"):
        next(it_redact)

    it_report = report_many(items)
    next(it_report)
    next(it_report)
    with pytest.raises(TypeError, match=r"item at index 2 must be a str, got int"):
        next(it_report)


# 15. non-string error does not reveal item repr/content
def test_non_string_error_does_not_reveal_content() -> None:
    secret_object = ["sensitive_payload_123456789"]
    it = redact_many(["سند ۱", secret_object])  # type: ignore[list-item]
    next(it)
    with pytest.raises(TypeError) as exc_info:
        next(it)

    err_msg = str(exc_info.value)
    assert "sensitive_payload_123456789" not in err_msg
    assert err_msg == "item at index 1 must be a str, got list"


# 16. input order preserved
def test_input_order_preserved() -> None:
    docs = [
        "سند A: کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "سند B: شماره ۰۹۱۲۳۴۵۶۷۸۹",
        "سند C: شبا IR641234567890123456789012",
    ]
    redacted = list(redact_many(docs))
    assert redacted[0] == "سند A: کد ملی [IR_NATIONAL_ID_1]"
    assert redacted[1] == "سند B: شماره [IR_MOBILE_1]"
    assert redacted[2] == "سند C: شبا [IR_IBAN_1]"


# 17. detect_many matches independent detect() results
def test_detect_many_matches_independent_detect() -> None:
    docs = [
        "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹",
        "بدون شناسه حساس",
        "شبا IR641234567890123456789012",
    ]
    batch_res = list(detect_many(docs))
    single_res = [detect(d) for d in docs]
    assert batch_res == single_res


# 18. redact_many matches independent redact() results
def test_redact_many_matches_independent_redact() -> None:
    docs = [
        "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹",
        "بدون شناسه حساس",
        "شبا IR641234567890123456789012",
    ]
    batch_res = list(redact_many(docs))
    single_res = [redact(d) for d in docs]
    assert batch_res == single_res


# 19. report_many matches independent detection_report() results
def test_report_many_matches_independent_detection_report() -> None:
    docs = [
        "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹",
        "متن بدون حساسیت",
        "شبا IR641234567890123456789012",
    ]
    batch_res = list(report_many(docs))
    single_res = [detection_report(d) for d in docs]
    assert batch_res == single_res


# 20. default detector semantics preserved
def test_default_detector_semantics_preserved() -> None:
    doc = (
        "ملی ۱۲۳۴۵۶۷۸۹۱، موبایل ۰۹۱۲۳۴۵۶۷۸۹، شبا IR641234567890123456789012، "
        "ایمیل test@example.com، کارت 1234567890123452"
    )
    res = list(detect_many([doc]))[0]
    types = {d.type for d in res}
    # Defaults must include IR_NATIONAL_ID, IR_MOBILE, IR_IBAN
    assert types == {"IR_NATIONAL_ID", "IR_MOBILE", "IR_IBAN"}
    # Opt-ins must NOT be included in default
    assert "EMAIL" not in types
    assert "BANK_CARD" not in types


# 21. detectors=[] preserved
def test_detectors_empty_list_preserved() -> None:
    doc = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹"
    assert list(detect_many([doc], detectors=[])) == [[]]
    assert list(redact_many([doc], detectors=[])) == [doc]
    rep = list(report_many([doc], detectors=[]))[0]
    assert rep.total_detections == 0


# 22. explicit detector replacement semantics preserved
def test_explicit_detector_replacement_semantics_preserved() -> None:
    doc = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و ایمیل test@example.com"
    email_det = EmailDetector()
    # Explicitly providing only EmailDetector replaces default detectors
    res = list(detect_many([doc], detectors=[email_det]))[0]
    assert len(res) == 1
    assert res[0].type == "EMAIL"


# 23. detector configuration snapshot immune to caller list mutation
def test_detector_configuration_snapshot_immune_to_mutation() -> None:
    detectors_list = [EmailDetector()]
    doc = "ایمیل user@example.com و کد ملی ۱۲۳۴۵۶۷۸۹۱"

    it = redact_many([doc], detectors=detectors_list)
    # Caller mutates list after creating iterator
    detectors_list.clear()

    # Redaction still uses snapshotted EmailDetector
    res = list(it)
    assert res == ["ایمیل [EMAIL_1] و کد ملی ۱۲۳۴۵۶۷۸۹۱"]


# 24. type_priority snapshot immune to caller mutation
def test_type_priority_snapshot_immune_to_mutation() -> None:
    overlap_text = "1234567890123452@example.com"
    dual_detectors: list[Detector] = [EmailDetector(), fa_redact.BankCardDetector()]
    priority_list = ["BANK_CARD", "EMAIL"]

    it = redact_many(
        [overlap_text],
        detectors=dual_detectors,
        conflict_policy="priority",
        type_priority=priority_list,
    )
    # Caller mutates list
    priority_list[0] = "EMAIL"
    priority_list[1] = "BANK_CARD"

    # Snapshotted configuration preserved (BANK_CARD wins)
    res = list(it)
    assert res == ["[BANK_CARD_1]@example.com"]


# 25. redaction conflict default remains reject
def test_redaction_conflict_default_remains_reject() -> None:
    overlap_text = "1234567890123452@example.com"
    dual_detectors: list[Detector] = [EmailDetector(), fa_redact.BankCardDetector()]

    it = redact_many([overlap_text], detectors=dual_detectors)
    with pytest.raises(ValueError, match="Overlapping detections"):
        list(it)


# 26. longest policy passes through
def test_longest_policy_passes_through() -> None:
    overlap_text = "1234567890123452@example.com"
    dual_detectors: list[Detector] = [EmailDetector(), fa_redact.BankCardDetector()]

    it = redact_many(
        [overlap_text],
        detectors=dual_detectors,
        conflict_policy="longest",
    )
    assert list(it) == ["[EMAIL_1]"]


# 27. priority policy passes through
def test_priority_policy_passes_through() -> None:
    overlap_text = "1234567890123452@example.com"
    dual_detectors: list[Detector] = [EmailDetector(), fa_redact.BankCardDetector()]

    it = redact_many(
        [overlap_text],
        detectors=dual_detectors,
        conflict_policy="priority",
        type_priority=["BANK_CARD", "EMAIL"],
    )
    assert list(it) == ["[BANK_CARD_1]@example.com"]


# 28. per-document placeholder numbering restarts
def test_per_document_placeholder_numbering_restarts() -> None:
    doc1 = "کد ملی ۱۲۳۴۵۶۷۸۹۱ و موبایل ۰۹۱۲۳۴۵۶۷۸۹"
    doc2 = "کد ملی دیگری: ۰۰۱۲۳۴۵۶۷۹ و موبایل ۰۹۳۵۱۲۳۴۵۶۷"

    redacted = list(redact_many([doc1, doc2]))
    assert redacted[0] == "کد ملی [IR_NATIONAL_ID_1] و موبایل [IR_MOBILE_1]"
    # Notice that counters restart from 1 for doc2:
    assert redacted[1] == "کد ملی دیگری: [IR_NATIONAL_ID_1] و موبایل [IR_MOBILE_1]"


# 29. repeated identifier inside one document remains consistent
def test_repeated_identifier_inside_one_document_consistent() -> None:
    doc = "ملی ۱۲۳۴۵۶۷۸۹۱ و تکرار 1234567891 و ملی دوم ۰۰۱۲۳۴۵۶۷۹"
    redacted = list(redact_many([doc]))[0]
    expected = (
        "ملی [IR_NATIONAL_ID_1] و تکرار [IR_NATIONAL_ID_1] و ملی دوم [IR_NATIONAL_ID_2]"
    )
    assert redacted == expected


# 30. same identifier across two documents is not relying on shared session
def test_same_identifier_across_documents_independent() -> None:
    doc1 = "کد ملی ۱۲۳۴۵۶۷۸۹۱ در سند اول"
    doc2 = "کد ملی ۱۲۳۴۵۶۷۸۹۱ در سند دوم"

    redacted = list(redact_many([doc1, doc2]))
    assert redacted[0] == "کد ملی [IR_NATIONAL_ID_1] در سند اول"
    assert redacted[1] == "کد ملی [IR_NATIONAL_ID_1] در سند دوم"


# 31. no PseudonymizationSession mapping exposed
def test_no_pseudonymization_session_mapping_exposed() -> None:
    import fa_redact.batch as batch_mod

    assert not hasattr(batch_mod, "mapping")
    assert not hasattr(batch_mod, "session")
    assert not hasattr(batch_mod, "PseudonymizationSession")


# 32. report_many returns DetectionReport
def test_report_many_returns_detection_report() -> None:
    doc = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    rep = list(report_many([doc]))[0]
    assert isinstance(rep, DetectionReport)
    assert rep.total_detections == 1
    assert rep.counts["IR_NATIONAL_ID"] == 1


# 33. reports remain value-free
def test_reports_remain_value_free() -> None:
    doc = "کد ملی ۱۲۳۴۵۶۷۸۹۱"
    rep = list(report_many([doc]))[0]
    rep_repr = repr(rep)
    assert "۱۲۳۴۵۶۷۸۹۱" not in rep_repr
    assert "1234567891" not in rep_repr


# 34. generator does not eagerly consume all source items
# 35. requesting first result consumes only first document
def test_laziness_sentinel_consumption() -> None:
    consumed: list[int] = []

    def source() -> Iterator[str]:
        consumed.append(0)
        yield "سند ۰: کد ملی ۱۲۳۴۵۶۷۸۹۱"
        consumed.append(1)
        yield "سند ۱: شماره ۰۹۱۲۳۴۵۶۷۸۹"
        consumed.append(2)
        raise AssertionError("Sentinel over-consumed!")

    it = detect_many(source())
    # Before consuming iterator, zero items should be read
    assert consumed == []

    first_res = next(it)
    assert len(first_res) == 1
    assert first_res[0].type == "IR_NATIONAL_ID"
    # Exactly one item consumed
    assert consumed == [0]

    second_res = next(it)
    assert len(second_res) == 1
    assert second_res[0].type == "IR_MOBILE"
    # Exactly two items consumed
    assert consumed == [0, 1]


# 36. error in later document occurs only when iteration reaches it
# 37. earlier yielded results remain yielded before later error
# 38. no batch-wide rollback claim/behavior
def test_partial_iteration_error_preserves_earlier_yields() -> None:
    docs: list[Any] = [
        "سند اول: کد ملی ۱۲۳۴۵۶۷۸۹۱",
        "سند دوم: شماره ۰۹۱۲۳۴۵۶۷۸۹",
        99999,  # invalid item
    ]
    it = redact_many(docs)

    res1 = next(it)
    assert res1 == "سند اول: کد ملی [IR_NATIONAL_ID_1]"

    res2 = next(it)
    assert res2 == "سند دوم: شماره [IR_MOBILE_1]"

    with pytest.raises(TypeError, match=r"item at index 2 must be a str, got int"):
        next(it)


# 39. caller-provided custom fake detector reused safely
def test_caller_provided_custom_detector_reused() -> None:
    fake = FakeCustomDetector(target_type="MY_PII")
    docs = [
        "متن اول با CUSTOM_ENTITY اینجا",
        "متن دوم بدون شناسه",
        "متن سوم با CUSTOM_ENTITY مجدد",
    ]
    res = list(detect_many(docs, detectors=[fake]))
    assert len(res) == 3
    assert len(res[0]) == 1 and res[0][0].type == "MY_PII"
    assert len(res[1]) == 0
    assert len(res[2]) == 1 and res[2][0].type == "MY_PII"
    assert fake.call_count == 3


# 40. fake explicit PERSON detector works through detect_many
def test_fake_person_detector_works_through_detect_many() -> None:
    person_det = FakePersonDetector()
    docs = ["مراجعه بیمار علی رضایی به کلینیک", "متن بدون نام"]
    res = list(detect_many(docs, detectors=[person_det]))
    assert len(res[0]) == 1
    assert res[0][0].type == "PERSON"
    assert res[0][0].value == "علی رضایی"
    assert len(res[1]) == 0


# 41. no PersianNERDetector auto-construction
def test_no_persian_ner_auto_construction() -> None:
    import fa_redact.batch as batch_mod

    assert not hasattr(batch_mod, "PersianNERDetector")


# 42. batch module import does not require torch/transformers
def test_batch_module_import_does_not_require_torch() -> None:
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


# 43. global default detector tuple unchanged
def test_global_default_detectors_unchanged() -> None:
    from fa_redact.pipeline import _DEFAULT_DETECTORS

    assert len(_DEFAULT_DETECTORS) == 3
    assert isinstance(_DEFAULT_DETECTORS[0], IranianNationalIDDetector)
    assert isinstance(_DEFAULT_DETECTORS[1], IranianMobileNumberDetector)
    assert isinstance(_DEFAULT_DETECTORS[2], IranianIBANDetector)


# 44. input texts are not mutated
def test_input_texts_not_mutated() -> None:
    original_list = ["سند ۱: کد ملی ۱۲۳۴۵۶۷۸۹۱", "سند ۲: شماره ۰۹۱۲۳۴۵۶۷۸۹"]
    copied = list(original_list)
    _ = list(redact_many(original_list))
    assert original_list == copied


# 45. helper retains no explicit history collection
def test_helper_retains_no_history() -> None:
    import inspect

    import fa_redact.batch as b_mod

    src = inspect.getsource(b_mod)
    assert "history" not in src
    assert "source_buffer" not in src
    assert "processed_texts" not in src


# 46. source version remains 0.3.0
def test_source_version_remains_0_3_0() -> None:
    assert fa_redact.__version__ == "0.3.0"


# 47. root exports detect_many
# 48. root exports redact_many
# 49. root exports report_many
def test_root_exports() -> None:
    assert hasattr(fa_redact, "detect_many")
    assert callable(fa_redact.detect_many)
    assert hasattr(fa_redact, "redact_many")
    assert callable(fa_redact.redact_many)
    assert hasattr(fa_redact, "report_many")
    assert callable(fa_redact.report_many)
    assert "detect_many" in fa_redact.__all__
    assert "redact_many" in fa_redact.__all__
    assert "report_many" in fa_redact.__all__


# 50. Submodule exports check
def test_submodule_exports() -> None:
    assert callable(sub_detect_many)
    assert callable(sub_redact_many)
    assert callable(sub_report_many)


# Static configuration validation eager check
def test_configuration_validation_timing() -> None:
    # Invalid conflict_policy fails immediately on helper call before iteration
    with pytest.raises(ValueError, match="Invalid conflict policy"):
        redact_many([], conflict_policy="invalid_policy")  # type: ignore[arg-type]

    # type_priority with reject policy fails immediately
    with pytest.raises(ValueError, match="type_priority is only valid"):
        redact_many([], conflict_policy="reject", type_priority=["IR_NATIONAL_ID"])

    # policy="priority" without type_priority fails immediately
    with pytest.raises(ValueError, match="type_priority must be provided"):
        redact_many([], conflict_policy="priority", type_priority=None)

    # invalid detectors container fails immediately
    with pytest.raises(TypeError, match="detectors must be a Sequence"):
        detect_many([], detectors=123)  # type: ignore[arg-type]
