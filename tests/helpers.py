from __future__ import annotations

import pandas as pd


def series(values, start: str = "2020-01-01") -> pd.Series:
    """영업일 인덱스의 종가 시계열을 만든다."""
    values = list(values)
    index = pd.bdate_range(start=start, periods=len(values))
    return pd.Series([float(v) for v in values], index=index)
