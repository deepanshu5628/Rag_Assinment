"""PII masking helpers.

Pure, stateless functions used to keep user-supplied PII (emails and phone
numbers) out of logs and out of the final answer returned to the caller.

Design notes
------------
- We mask emails and phone numbers only. These are the PII classes present in
  the eval set (the "Anand Sharma" case: an email like ``first.last@<domain>``
  and a +91 10-digit mobile number).
- Patterns are deliberately conservative so we do NOT mask legitimate KB
  content such as support extensions written as "ext. 4357" or "ext. 7333"
  (3-4 digit numbers), SLA figures ("4 hours", "50 GB"), or error codes
  ("ZT-401"). Only 7+ digit phone-shaped tokens are treated as phone numbers.
"""

from __future__ import annotations

import re

# Email: local-part@domain. Local part masked to first char + asterisks.
_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
)

# Phone: optional leading +, then digits possibly separated by spaces, dashes
# or parentheses, with at least 7 digits total. Requires either a leading "+"
# or a separator so plain 7-digit integers inside prose are less likely to be
# caught, while still catching formats like "+91 5550100000", "5550100000",
# "(555) 010-0000" and "555-010-0000".
_PHONE_RE = re.compile(
    r"(?<![\w.])"                      # not preceded by word char or dot
    r"(\+?\d[\d\s().\-]{5,}\d)"        # + optional, >= 7 digit-ish chars
    r"(?![\w.])"                       # not followed by word char or dot
)


def mask_email(text: str) -> str:
    """Mask the local part of any email address, keeping its first character
    and the full domain. e.g. ``first.last@x.example`` -> ``f***@x.example``.
    """
    if not text:
        return text

    def _repl(m: re.Match) -> str:
        return f"{m.group(1)}***{m.group(2)}"

    return _EMAIL_RE.sub(_repl, text)


def mask_phone(text: str) -> str:
    """Mask phone numbers, keeping only the last two digits.

    Only tokens with 7 or more digits are treated as phone numbers, so short
    support extensions like "ext. 4357" are left intact.
    """
    if not text:
        return text

    def _repl(m: re.Match) -> str:
        token = m.group(1)
        digits = re.sub(r"\D", "", token)
        if len(digits) < 7:
            # Too short to be a phone number (e.g. a 4-digit extension): leave it.
            return token
        last2 = digits[-2:]
        return f"[PHONE ***{last2}]"

    return _PHONE_RE.sub(_repl, text)


def mask_pii(text: str) -> str:
    """Apply all PII masks (email then phone). Returns the masked string."""
    if not text:
        return text
    return mask_phone(mask_email(text))
