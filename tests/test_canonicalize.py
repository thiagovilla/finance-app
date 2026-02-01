from __future__ import annotations

from finance_cli.db import canonicalize_description


def test_canonicalize_removes_installment_suffixes() -> None:
    assert canonicalize_description("ACL ODONTO SAUD03 04") == "acl odonto"
    assert canonicalize_description("ACL ODONTO SAUD04/04") == "acl odonto"


def test_canonicalize_collapses_spaced_letters() -> None:
    assert canonicalize_description("A C L ODONTO") == "acl odonto"
