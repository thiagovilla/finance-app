import pytest

from finance_cli.itau import (
    apply_id_schema,
    _blocks_to_statements,
    check_total,
    _flip_sign_last_column,
    load_existing_rows,
    _match_to_csv,
    extract_total,
    write_csv_lines_idempotent,
    _apply_marker,
    Line,
)


def test_match_to_csv_inserts_year_and_normalizes() -> None:
    raw = "01/02\nUber   Trip\n  -  12,34"
    result = _match_to_csv(raw, "25")
    assert result == "01/02/25,Uber Trip,-12.34"


def test_blocks_to_statements_extracts_lines() -> None:
    block = "01/02\nCoffee\n  10,00\n\n05/02\nMarket\n  20,50"
    result = _blocks_to_statements([block], "24", None)
    assert result == [
        "0,01/02/24,,Coffee,10.00",
        "1,05/02/24,,Market,20.50",
    ]


def test_blocks_to_statements_normalizes_spaced_date_line() -> None:
    block = "19/1 2\nPOSTO SAO JOSELEMEBRA\n  5,00"
    result = _blocks_to_statements([block], "24", None)
    assert result == ["0,19/12/24,,POSTO SAO JOSELEMEBRA,5.00"]


def test_blocks_to_statements_handles_thousands_amount() -> None:
    block = "22/12\nCASASBA*CASAS BAHIA\n- 2.249,00"
    result = _blocks_to_statements([block], "24", None)
    assert result == ["0,22/12/24,,CASASBA*CASAS BAHIA,-2249.00"]


def test_blocks_to_statements_handles_installment_line() -> None:
    block = "15/01\nDELL\n12/12\n61,75"
    result = _blocks_to_statements([block], "24", None)
    assert result == ["0,15/01/24,,DELL 12/12,61.75"]


def test_blocks_to_statements_handles_multiline_description() -> None:
    block = "24/11\nEBN\n*SPOTIFYCUR\n23,90"
    result = _blocks_to_statements([block], "25", None)
    assert result == ["0,24/11/25,,EBN *SPOTIFYCUR,23.90"]


def test_blocks_to_statements_captures_category_location_enhanced() -> None:
    block = (
        "25/11\nAzul Linhas Aereas BraB\n156,60\n"
        "19/1 1\nNOEL LAZA RO TAUFIC CINL\n20,00\n"
        "AIRLINE BARUERI\n"
        "lazer LEME\n"
    )
    result = _blocks_to_statements([block], "25", None, enhanced=True)
    assert result == [
        "0,25/11/25,,Azul Linhas Aereas BraB,156.60,AIRLINE,BARUERI",
        "1,19/11/25,,NOEL LAZA RO TAUFIC CINL,20.00,lazer,LEME",
    ]


def test_blocks_to_statements_handles_spaced_date() -> None:
    block = "19/1 2\nPOSTO SAO JOSELEMEBRA\n  5,00"
    result = _blocks_to_statements([block], "24", None)
    assert result == ["0,19/12/24,,POSTO SAO JOSELEMEBRA,5.00"]



def test_flip_sign_last_column() -> None:
    rows = [
        "0,01/02/24,,Coffee,10.00",
        "1,02/02/24,,Refund,-5.00",
    ]
    assert _flip_sign_last_column(rows) == [
        "0,01/02/24,,Coffee,-10.0",
        "1,02/02/24,,Refund,5.0",
    ]


def test_apply_id_schema_uses_payment_date_month() -> None:
    rows = ["0,01/02/24,15/03/24,Coffee,10.00"]
    assert apply_id_schema(rows, "en-us") == [
        "2024-MAR-1,01/02/24,15/03/24,Coffee,10.00"
    ]


def test_check_total_ok() -> None:
    rows = ["0,01/02/24,,Coffee,10.00", "1,02/02/24,,Market,5.50"]
    check_total(rows, 15.5)


def test_check_total_mismatch() -> None:
    rows = ["0,01/02/24,,Coffee,10.00", "1,02/02/24,,Market,5.50"]
    with pytest.raises(ValueError, match="Total mismatch"):
        check_total(rows, 10.0)


def test_find_total_in_text_picks_last_match() -> None:
    text = (
        "Total da fatura anterior\n1.234,56\n"
        "Other\n"
        "Total desta fatura\n10.532,52"
    )
    assert extract_total(text) == 10532.52


def test_find_total_in_text_handles_spaced_label() -> None:
    text = (
        "O tota l da sua fatura e:\n"
        "Com vencimento em:\n"
        "Limite total de credito:\n"
        "R$ 9.356,73\n"
        "06/01/2026\n"
        "R$ 18.412,00\n"
    )
    assert extract_total(text) == 9356.73


def test_write_csv_lines_idempotent(tmp_path) -> None:
    output_path = tmp_path / "itau_pdf.csv"
    rows = ["0,01/02/24,,Coffee,-10.0", "1,02/02/24,,Market,-5.0"]
    added_first = write_csv_lines_idempotent(rows, output_path, include_headers=False)
    added_second = write_csv_lines_idempotent(rows, output_path, include_headers=False)

    assert added_first == 2
    assert added_second == 0

    existing = load_existing_rows(output_path)
    assert existing == set(rows)


def test_apply_marker_respects_start_marker() -> None:
    left_lines = [
        Line(y0=10, x0=0, y1=12, x1=10, text="header"),
        Line(y0=20, x0=0, y1=22, x1=10, text="row1"),
        Line(y0=30, x0=0, y1=32, x1=10, text="row2"),
    ]
    right_lines = [
        Line(y0=15, x0=0, y1=17, x1=10, text="header"),
        Line(y0=30, x0=0, y1=32, x1=10, text="row3"),
    ]
    marker = {"left": 28.0, "right": None, "start_left": 15.0, "start_right": 25.0}
    filtered_left, filtered_right = _apply_marker(
        {"left": left_lines, "right": right_lines}, marker
    )
    assert [line.text for line in filtered_left] == ["row1"]
    assert filtered_right == []
