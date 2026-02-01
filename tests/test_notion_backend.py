from __future__ import annotations

from pathlib import Path

from finance_cli.notion_backend import derive_account_from_filename, normalize_account_name


def test_derive_account_from_filename() -> None:
    path = Path("Itau_7180_2025_02.csv")
    assert derive_account_from_filename(path) == "Itaú 7180"


def test_normalize_account_name_cc() -> None:
    assert normalize_account_name("nubank cc") == "Nubank CC"
