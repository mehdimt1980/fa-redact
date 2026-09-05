"""Tests for conservative ASCII Internet Email validator."""

import pytest

from fa_redact.validators.email import is_valid_email


class TestEmailValidatorValidCases:
    """Test valid conservative ASCII email addresses."""

    @pytest.mark.parametrize(
        "email",
        [
            "alice@example.com",
            "first.last@example.com",
            "first.last+tag@example.com",
            "user_name@example.org",
            "customer-42@example.co.uk",
            "a@b.co",
            "UPPER.CASE@EXAMPLE.COM",
            "billing+hospital@example-health.org",
            "user.name+tag1-tag2@sub.domain.example.com",
            "test!#$%&'*+-/=?^_`{|}~@example.com",
            "a.b.c.d@e.f.g.org",
            "nurse1@hospital-system.org",
            "patient_support@sub-dept.medical-center.org",
            "user@example.xn--p1ai",  # valid punycode TLD
        ],
    )
    def test_valid_emails(self, email: str) -> None:
        assert is_valid_email(email) is True


class TestEmailValidatorInvalidLocalPart:
    """Test rejection of invalid local parts."""

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "@example.com",
            ".alice@example.com",
            "alice.@example.com",
            "alice..smith@example.com",
            "alice...smith@example.com",
            '"alice"@example.com',
            '"john doe"@example.com',
            "john doe@example.com",
            "alice@smith@example.com",
            "alice(comment)@example.com",
            "alice[test]@example.com",
            "alice,smith@example.com",
            "alice:smith@example.com",
            "alice;smith@example.com",
            "alice<test>@example.com",
            "alice\\escape@example.com",
        ],
    )
    def test_invalid_local_part(self, email: str) -> None:
        assert is_valid_email(email) is False


class TestEmailValidatorInvalidDomain:
    """Test rejection of invalid domains."""

    @pytest.mark.parametrize(
        "email",
        [
            "alice@",
            "alice@localhost",  # single-label domain
            "alice@hospital",  # single-label domain
            "alice@-example.com",  # label starts with hyphen
            "alice@example-.com",  # label ends with hyphen
            "alice@example..com",  # empty label / double dot
            "alice@.example.com",  # leading dot
            "alice@example.com.",  # trailing dot
            "alice@exa_mple.com",  # underscore in domain label
            "alice@example.c",  # 1-letter TLD
            "alice@example.123",  # numeric TLD
            "alice@example.c-m",  # hyphen in standard TLD (not xn--)
            "alice@[192.0.2.1]",  # IPv4 literal
            "alice@[IPv6:2001:db8::1]",  # IPv6 literal
            "alice@domain",  # no dot
        ],
    )
    def test_invalid_domain(self, email: str) -> None:
        assert is_valid_email(email) is False


class TestEmailValidatorUnsupportedUnicodeEAI:
    """Test explicit rejection of Unicode / EAI / Persian digit emails."""

    @pytest.mark.parametrize(
        "email",
        [
            "کاربر@example.com",
            "alice@مثال.ir",
            "user۱۲@example.com",
            "۱۲۳۴@example.com",
            "user@دامین.com",
            "تست@تست.ایران",
            "user@éxample.com",
            "userñ@example.com",
        ],
    )
    def test_unsupported_unicode_and_eai(self, email: str) -> None:
        assert is_valid_email(email) is False


class TestEmailValidatorFormattingAndWhitespace:
    """Test that input is not stripped or trimmed."""

    @pytest.mark.parametrize(
        "email",
        [
            " alice@example.com",
            "alice@example.com ",
            " alice@example.com ",
            "alice @example.com",
            "alice@ example.com",
            "\talice@example.com",
            "alice@example.com\n",
            "alice\r\n@example.com",
            "Alice Example <alice@example.com>",
            "<alice@example.com>",
        ],
    )
    def test_whitespace_and_display_names_rejected(self, email: str) -> None:
        assert is_valid_email(email) is False


class TestEmailValidatorNonStringInputs:
    """Test non-string inputs return False safely."""

    @pytest.mark.parametrize(
        "val",
        [
            None,
            123,
            123.456,
            [],
            ["alice@example.com"],
            {},
            {"email": "alice@example.com"},
            True,
            False,
            b"alice@example.com",
        ],
    )
    def test_non_string_inputs(self, val: object) -> None:
        assert is_valid_email(val) is False  # type: ignore[arg-type]


class TestEmailValidatorLengthLimits:
    """Test RFC and practical length boundaries."""

    def test_local_part_exact_64_chars_is_valid(self) -> None:
        local_64 = "a" * 64
        email = f"{local_64}@example.com"
        assert len(local_64) == 64
        assert is_valid_email(email) is True

    def test_local_part_65_chars_is_invalid(self) -> None:
        local_65 = "a" * 65
        email = f"{local_65}@example.com"
        assert len(local_65) == 65
        assert is_valid_email(email) is False

    def test_domain_label_exact_63_chars_is_valid(self) -> None:
        label_63 = "a" * 63
        email = f"alice@{label_63}.com"
        assert len(label_63) == 63
        assert is_valid_email(email) is True

    def test_domain_label_64_chars_is_invalid(self) -> None:
        label_64 = "a" * 64
        email = f"alice@{label_64}.com"
        assert len(label_64) == 64
        assert is_valid_email(email) is False

    def test_total_length_boundary_254(self) -> None:
        # local: 64 chars
        # @: 1 char
        # domain: 189 chars (e.g. 63.63.59.com = 63 + 1 + 63 + 1 + 57 + 1 + 3 = 189)
        # Total: 64 + 1 + 189 = 254 chars
        label1 = "a" * 63
        label2 = "b" * 63
        label3 = "c" * 57
        tld = "com"
        domain = f"{label1}.{label2}.{label3}.{tld}"
        local = "u" * 64
        email_254 = f"{local}@{domain}"

        assert len(email_254) == 254
        assert is_valid_email(email_254) is True

        # Total 255 chars
        email_255 = f"{local}x@{domain}"
        assert len(email_255) == 255
        assert is_valid_email(email_255) is False
