from pathlib import Path

import pandas as pd

from finance_cli.nu import parse_nubank_csv


def test_parse_nubank_cc(tmp_path: Path) -> None:
    csv_path = tmp_path / "nubank_cc.csv"
    df = pd.DataFrame(
        {
            "date": ["02/01/2025", "03/02/2025"],
            "description": ["Coffee", "Groceries"],
            "amount": [10.0, -20.5],
            "category": ["Food", "Market"],
        }
    )
    df.to_csv(csv_path, index=False)

    output = parse_nubank_csv(csv_path, template="nubank_cc")

    result = pd.read_csv(output)
    assert list(result.columns) == [
        "id",
        "transaction_date",
        "payment_date",
        "description",
        "amount",
        "category",
    ]
    assert result.loc[0, "transaction_date"] == "2025-01-02"
    assert result.loc[1, "transaction_date"] == "2025-02-03"
    assert result.loc[0, "amount"] == -10.0
    assert result.loc[1, "amount"] == 20.5


def test_parse_nubank_chk(tmp_path: Path) -> None:
    input_path = tmp_path / "nubank_chk.csv"
    output_path = tmp_path / "parsed.csv"

    pd.DataFrame(
        {
            "data": ["02/01/2025"],
            "descricao": ["Salary"],
            "valor": [1500.0],
        }
    ).to_csv(input_path, index=False)

    parse_nubank_csv(input_path, output_path, template="nubank_chk")

    result = pd.read_csv(output_path)
    assert result.loc[0, "transaction_date"] == "2025-01-02"
    assert result.loc[0, "amount"] == 1500.0
