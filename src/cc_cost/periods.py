"""本日/今月/先月/先々月の4つの固定期間の境界判定(実行環境のローカルタイムゾーン基準)。"""

from __future__ import annotations

import dataclasses
import datetime as dt

PERIOD_KEYS = ("today", "this_month", "last_month", "two_months_ago")

PERIOD_LABELS = {
    "today": "本日",
    "this_month": "今月",
    "last_month": "先月",
    "two_months_ago": "先々月",
}


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


@dataclasses.dataclass(frozen=True)
class PeriodRanges:
    today: dt.date
    this_month_start: dt.date
    last_month_start: dt.date
    last_month_end: dt.date  # exclusive
    two_months_ago_start: dt.date
    two_months_ago_end: dt.date  # exclusive

    @classmethod
    def for_now(cls, now: dt.datetime) -> "PeriodRanges":
        y, m = now.year, now.month
        this_month_start = dt.date(y, m, 1)
        ly, lm = _shift_month(y, m, -1)
        last_month_start = dt.date(ly, lm, 1)
        tmy, tmm = _shift_month(y, m, -2)
        two_months_ago_start = dt.date(tmy, tmm, 1)
        return cls(
            today=now.date(),
            this_month_start=this_month_start,
            last_month_start=last_month_start,
            last_month_end=this_month_start,
            two_months_ago_start=two_months_ago_start,
            two_months_ago_end=last_month_start,
        )

    def periods_for(self, local_date: dt.date) -> list[str]:
        """1つの日付が属する期間キーの一覧を返す(複数の期間に同時に属してよい)。"""
        keys = []
        if local_date == self.today:
            keys.append("today")
        if local_date >= self.this_month_start:
            keys.append("this_month")
        if self.last_month_start <= local_date < self.last_month_end:
            keys.append("last_month")
        if self.two_months_ago_start <= local_date < self.two_months_ago_end:
            keys.append("two_months_ago")
        return keys
