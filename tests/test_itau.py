import pytest

from finance_cli.itau import (
    blocks_to_statements,
    check_total,
    flip_sign_last_column,
    load_existing_rows,
    match_to_csv,
    find_total_in_text,
    write_csv_lines_idempotent,
)


def test_match_to_csv_inserts_year_and_normalizes() -> None:
    raw = "01/02\nUber   Trip\n  -  12,34"
    result = match_to_csv(raw, "25")
    assert result == "01/02/25,Uber Trip,-12.34"


def test_blocks_to_statements_extracts_lines() -> None:
    block = "01/02\nCoffee\n  10,00\n\n05/02\nMarket\n  20,50"
    result = blocks_to_statements([block], "24")
    assert result == ["01/02/24,Coffee,10.00", "05/02/24,Market,20.50"]


def test_flip_sign_last_column() -> None:
    rows = ["01/02/24,Coffee,10.00", "02/02/24,Refund,-5.00"]
    assert flip_sign_last_column(rows) == ["01/02/24,Coffee,-10.0", "02/02/24,Refund,5.0"]


def test_check_total_ok() -> None:
    rows = ["01/02/24,Coffee,10.00", "02/02/24,Market,5.50"]
    check_total(rows, 15.5)


def test_check_total_mismatch() -> None:
    rows = ["01/02/24,Coffee,10.00", "02/02/24,Market,5.50"]
    with pytest.raises(ValueError, match="Total mismatch"):
        check_total(rows, 10.0)


def test_find_total_in_text_picks_last_match() -> None:
    text = (
        "Total da fatura anterior\n1.234,56\n"
        "Other\n"
        "Total desta fatura\n10.532,52"
    )
    assert find_total_in_text(text) == 10532.52


def test_write_csv_lines_idempotent(tmp_path) -> None:
    output_path = tmp_path / "itau.csv"
    rows = ["01/02/24,Coffee,-10.0", "02/02/24,Market,-5.0"]
    added_first = write_csv_lines_idempotent(rows, output_path)
    added_second = write_csv_lines_idempotent(rows, output_path)

    assert added_first == 2
    assert added_second == 0

    existing = load_existing_rows(output_path)
    assert existing == set(rows)
