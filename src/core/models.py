from dataclasses import dataclass, asdict
from datetime import date


@dataclass(frozen=True)
class Statement:
    id: str
    transaction_date: date
    description: str
    amount: float
    payment_date: date | None = None
    category: str = ""
    location: str = ""
    tags: str = ""
    account: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert dates to ISO format (YYYY-MM-DD)
        data["transaction_date"] = self.transaction_date.isoformat()
        data["payment_date"] = self.payment_date.isoformat() or ""
        # Ensure amount is formatted to 2 decimal places
        data["amount"] = f"{self.amount:.2f}"
        return data