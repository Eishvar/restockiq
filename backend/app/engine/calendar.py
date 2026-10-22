"""Calendar features: what is special about each date (periods, public holidays, local events).

Pure functions, no database. Everything restaurant-specific comes in as data (labels such as
semester / break / intake, school_holidays, ramadan, peak_season ...).
"""
from datetime import timedelta

import numpy as np
import pandas as pd


def calendar_features(cal: pd.DataFrame, dates) -> pd.DataFrame:
    """One row per date with:

    - state:   sorted combination of the period labels active that day ("break+intake"), "normal" if none
    - holiday: True on a public holiday and the day before / after it (people shift their habits)
    - event:   True during a local event
    - names:   tuple of the holiday / event names touching that date (for the "why" chips)

    `cal` has columns type (period | public_holiday | local_event), label, start_date, end_date, name.
    """
    dates = pd.DatetimeIndex(dates)
    n = len(dates)
    labels: list[set[str]] = [set() for _ in range(n)]
    holiday = np.zeros(n, dtype=bool)
    event = np.zeros(n, dtype=bool)
    names: list[list[str]] = [[] for _ in range(n)]

    for e in cal.itertuples(index=False):
        start, end = pd.Timestamp(e.start_date), pd.Timestamp(e.end_date)
        if e.type == "period":
            if isinstance(e.label, str) and e.label:
                for i in np.flatnonzero((dates >= start) & (dates <= end)):
                    labels[i].add(e.label)
        elif e.type == "public_holiday":
            hit = np.flatnonzero((dates >= start - timedelta(days=1)) & (dates <= end + timedelta(days=1)))
            holiday[hit] = True
            for i in hit:
                names[i].append(e.name)
        elif e.type == "local_event":
            hit = np.flatnonzero((dates >= start) & (dates <= end))
            event[hit] = True
            for i in hit:
                names[i].append(e.name)

    return pd.DataFrame(
        {
            "state": ["+".join(sorted(s)) or "normal" for s in labels],
            "holiday": holiday,
            "event": event,
            "names": [tuple(x) for x in names],
        },
        index=dates,
    )
