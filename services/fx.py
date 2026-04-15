from services.db import db


def get_fx_rate(from_ccy: str, to_ccy: str) -> float:
    if from_ccy == to_ccy:
        return 1.0
    for rate in db.get_fx_rates():
        if rate["baseCurrency"] == from_ccy and rate["quoteCurrency"] == to_ccy:
            return float(rate["rate"])
        if rate["baseCurrency"] == to_ccy and rate["quoteCurrency"] == from_ccy:
            r = float(rate["rate"])
            return 1.0 / r if r != 0 else 1.0
    return 1.0


def convert_amount(amount: float, from_ccy: str, to_ccy: str) -> float:
    return amount * get_fx_rate(from_ccy, to_ccy)
