"""Unit tests for pii.py (no DB, no network)."""

from pii import mask_email, mask_phone, mask_pii


def test_email_masked():
    out = mask_email("contact first.last@vectralogistics.example please")
    assert "first.last@vectralogistics.example" not in out
    assert "@vectralogistics.example" in out
    assert out.startswith("contact f***@")


def test_phone_masked_10_digit():
    out = mask_phone("call +91 5550100042 now")
    assert "5550100042" not in out
    assert "42" in out  # last two digits kept


def test_extension_left_intact():
    # 4-digit support extension must NOT be masked.
    text = "P1 tickets are phoned to ext. 4357"
    assert mask_phone(text) == text
    assert mask_pii(text) == text


def test_no_pii_unchanged():
    text = "Mailbox quota is 50 GB and resolves in 8 hours"
    assert mask_pii(text) == text


def test_mask_pii_combines_both():
    out = mask_pii("Caller a.b@x.example / +91 5550100042")
    assert "a.b@x.example" not in out
    assert "5550100042" not in out
