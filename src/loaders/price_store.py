"""The committed US price store.

Layout under ``data/prices/`` (git is the store; owner, 10 Nov 2026):

  YYYY.parquet          closed years
  YYYY-MM.parquet       closed months of the current year
  daily/YYYY-MM-DD.parquet  each session of the current month
  actions.csv           Date, Symbol, Dividend, Split (from Yahoo)

Rows are long: Date, Symbol, High, Low, Close, Volume. Close/High/Low are
Yahoo's SPLIT-adjusted prices. Dividend adjustment is computed on load from
``actions.csv`` (``adjusted_close``) rather than stored, because Yahoo's
dividend-adjusted close restates every earlier row on every ex-date: storing it
would rewrite every year's file several times a week. A split also restates the
history; the sync handles that by rewriting the symbol everywhere it appears.

Open is not stored: nothing in the strategy reads it (Paresh's sources were
close-only, and the charts draw closes).
"""

from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRICES_DIR = os.path.join(ROOT, "data", "prices")
DAILY_DIR = os.path.join(PRICES_DIR, "daily")
ACTIONS_FILE = os.path.join(PRICES_DIR, "actions.csv")

PRICE_COLS = ["High", "Low", "Close"]
COLUMNS = ["Date", "Symbol", *PRICE_COLS, "Volume"]
ACTION_COLS = ["Date", "Symbol", "Dividend", "Split"]

_YEAR = re.compile(r"^(\d{4})\.parquet$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})\.parquet$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.parquet$")


# ── shape ────────────────────────────────────────────────────────────────────
def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Canonical dtypes and order, so two writes of the same data are the same
    bytes and a rerun of the sync commits nothing."""
    if df is None or df.empty:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in
                             zip(COLUMNS, ["datetime64[ns]", "str", "float32", "float32", "float32", "int64"])})
    out = df[COLUMNS].copy()
    out["Date"] = pd.to_datetime(out["Date"]).dt.tz_localize(None).astype("datetime64[ns]").dt.normalize()
    out["Symbol"] = out["Symbol"].astype(str)
    for c in PRICE_COLS:
        out[c] = out[c].astype("float32")
    out["Volume"] = pd.to_numeric(out["Volume"], errors="coerce").fillna(0).astype("int64")
    out = out.dropna(subset=["Close"])
    out = out.drop_duplicates(["Date", "Symbol"], keep="last")
    return out.sort_values(["Date", "Symbol"]).reset_index(drop=True)


def write(df: pd.DataFrame, path: str) -> bool:
    """Write ``df`` to ``path`` only if the content changed. Returns True if written."""
    df = normalise(df)
    if os.path.exists(path):
        try:
            if normalise(pd.read_parquet(path)).equals(df):
                return False
        except Exception:  # noqa: BLE001 - an unreadable file is rewritten
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    df.to_parquet(tmp, index=False, compression="zstd", compression_level=9)
    os.replace(tmp, path)
    return True


# ── files ────────────────────────────────────────────────────────────────────
def files(prices_dir: str = PRICES_DIR) -> dict[str, list[str]]:
    years, months, days = [], [], []
    for p in sorted(glob.glob(os.path.join(prices_dir, "*.parquet"))):
        n = os.path.basename(p)
        if _YEAR.match(n):
            years.append(p)
        elif _MONTH.match(n):
            months.append(p)
    for p in sorted(glob.glob(os.path.join(prices_dir, "daily", "*.parquet"))):
        if _DAY.match(os.path.basename(p)):
            days.append(p)
    return {"years": years, "months": months, "days": days}


def file_for(day: pd.Timestamp, today: pd.Timestamp, prices_dir: str = PRICES_DIR) -> str:
    """Where a session's rows belong, given which periods are closed by ``today``."""
    day, today = pd.Timestamp(day), pd.Timestamp(today)
    if day.year < today.year:
        return os.path.join(prices_dir, f"{day.year}.parquet")
    if (day.year, day.month) < (today.year, today.month):
        return os.path.join(prices_dir, f"{day:%Y-%m}.parquet")
    return os.path.join(prices_dir, "daily", f"{day:%Y-%m-%d}.parquet")


def read_long(prices_dir: str = PRICES_DIR, start: str | None = None) -> pd.DataFrame:
    f = files(prices_dir)
    paths = f["years"] + f["months"] + f["days"]
    if start:
        y0 = pd.Timestamp(start).year
        paths = [p for p in paths if int(os.path.basename(p)[:4]) >= y0]
    if not paths:
        return normalise(None)
    return normalise(pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))


def read_columns(columns: list[str], prices_dir: str = PRICES_DIR, start: str | None = None,
                 symbols=None) -> pd.DataFrame:
    """A light read for the app: only ``columns`` (plus Date, Symbol), rows from
    ``start``, only ``symbols``; no re-sorting or dtype normalisation, which on
    the whole store doubles the peak memory of a cold start."""
    f = files(prices_dir)
    paths = f["years"] + f["months"] + f["days"]
    if start:
        y0 = pd.Timestamp(start).year
        paths = [p for p in paths if int(os.path.basename(p)[:4]) >= y0]
    cols = ["Date", "Symbol", *[c for c in columns if c not in ("Date", "Symbol")]]
    keep = set(symbols) if symbols is not None else None
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    tables = []
    for p in paths:
        # Symbol as a dictionary column: six million short strings as Python
        # objects were most of a cold start's peak memory.
        t = pq.read_table(p, columns=cols, read_dictionary=["Symbol"])
        if start:
            t = t.filter(pc.greater_equal(t["Date"], pa.scalar(pd.Timestamp(start), type=t.schema.field("Date").type)))
        if keep is not None:
            t = t.filter(pc.is_in(pc.cast(t["Symbol"], pa.string()), value_set=pa.array(sorted(keep))))
        tables.append(t)
    if not tables:
        return pd.DataFrame(columns=cols)
    return pa.concat_tables(tables).unify_dictionaries().combine_chunks().to_pandas()


def read_wide(columns: list[str], prices_dir: str = PRICES_DIR, start: str | None = None,
              symbols=None, dtype: str = "float64") -> dict[str, pd.DataFrame]:
    """Wide frames (Date x Symbol) for each of ``columns``, pivoted one partition
    file at a time so the six-million-row long table never exists at once (on
    the whole store that table was 400 MB of a cold start's peak)."""
    f = files(prices_dir)
    paths = f["years"] + f["months"] + f["days"]
    if start:
        y0 = pd.Timestamp(start).year
        paths = [p for p in paths if int(os.path.basename(p)[:4]) >= y0]
    keep = list(dict.fromkeys(symbols)) if symbols is not None else None
    pieces: dict[str, list[pd.DataFrame]] = {c: [] for c in columns}
    for p in paths:
        df = pd.read_parquet(p, columns=["Date", "Symbol", *columns])
        if start:
            df = df[df["Date"] >= pd.Timestamp(start)]
        if keep is not None:
            df = df[df["Symbol"].isin(set(keep))]
        for c in columns:
            pieces[c].append(df.pivot(index="Date", columns="Symbol", values=c))
        del df
    out = {}
    for c in columns:
        if not pieces[c]:
            out[c] = pd.DataFrame()
            continue
        w = pd.concat(pieces[c], axis=0, sort=False)
        pieces[c] = []
        if keep is not None:
            w = w.reindex(columns=[s for s in keep if s in w.columns])
        w = w[~w.index.duplicated(keep="last")].sort_index().astype(dtype)
        w.index.name = "Date"
        w.columns.name = None
        out[c] = w
    return out


def store(long: pd.DataFrame, today, prices_dir: str = PRICES_DIR) -> list[str]:
    """Write ``long`` into the partition files it belongs to, merged with what is
    there (new rows win). Returns the paths written."""
    long = normalise(long)
    if long.empty:
        return []
    written = []
    keys = long["Date"].map(lambda d: file_for(d, today, prices_dir))
    for path, part in long.groupby(keys, sort=True):
        old = pd.read_parquet(path) if os.path.exists(path) else None
        merged = part if old is None else pd.concat([normalise(old), part], ignore_index=True)
        if write(merged, path):
            written.append(path)
    return written


def replace_symbol(symbol: str, history: pd.DataFrame, today, prices_dir: str = PRICES_DIR) -> list[str]:
    """Replace every stored row of ``symbol`` with ``history`` (after a split
    restated it). Files the symbol is in but ``history`` does not reach lose
    the symbol's rows."""
    history = normalise(history)
    written = []
    f = files(prices_dir)
    for path in f["years"] + f["months"] + f["days"]:
        df = normalise(pd.read_parquet(path))
        if not (df["Symbol"] == symbol).any():
            continue
        if write(df[df["Symbol"] != symbol], path):
            written.append(path)
    written += store(history, today, prices_dir)
    return sorted(set(written))


def roll_up(today, prices_dir: str = PRICES_DIR) -> list[str]:
    """Merge closed days into their month and closed months into their year.
    Idempotent: a period is merged only once it is closed by ``today``."""
    today = pd.Timestamp(today)
    changed: list[str] = []
    f = files(prices_dir)
    for path in f["days"] + f["months"]:
        n = os.path.basename(path)
        y = int(n[:4])
        m = int(n[5:7])
        closed_month = (y, m) < (today.year, today.month)
        is_day = path in f["days"]
        if is_day and closed_month or (not is_day and y < today.year):
            target = file_for(pd.Timestamp(year=y, month=m, day=1), today, prices_dir)
            old = pd.read_parquet(target) if os.path.exists(target) else None
            part = pd.read_parquet(path)
            merged = part if old is None else pd.concat([old, part], ignore_index=True)
            write(merged, target)
            os.remove(path)
            changed += [target, path]
    return changed


# ── actions ──────────────────────────────────────────────────────────────────
def read_actions(path: str = ACTIONS_FILE) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=ACTION_COLS)
    a = pd.read_csv(path, parse_dates=["Date"])
    return a[ACTION_COLS]


def write_actions(actions: pd.DataFrame, path: str = ACTIONS_FILE) -> bool:
    a = actions[ACTION_COLS].copy()
    a["Date"] = pd.to_datetime(a["Date"]).dt.tz_localize(None).dt.normalize()
    a["Dividend"] = a["Dividend"].astype(float).round(6)
    a["Split"] = a["Split"].astype(float).round(6)
    a = a[(a["Dividend"] != 0) | (a["Split"] != 0)]
    a = a.drop_duplicates(["Date", "Symbol"], keep="last").sort_values(["Symbol", "Date"])
    text = a.to_csv(index=False, date_format="%Y-%m-%d")
    if os.path.exists(path) and open(path).read() == text:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)
    return True


# ── wide frames for the engine ───────────────────────────────────────────────
def wide(long: pd.DataFrame, column: str) -> pd.DataFrame:
    if isinstance(long["Symbol"].dtype, pd.CategoricalDtype):
        # A pivot on a categorical builds every category, observed or not, and
        # unstack keeps them; one code per row is far lighter than a string.
        sym = long["Symbol"].cat.remove_unused_categories()
        dates, d_codes = pd.factorize(long["Date"], sort=True)
        import numpy as np

        arr = np.full((len(d_codes), len(sym.cat.categories)), np.nan, dtype="float64")
        arr[dates, sym.cat.codes.to_numpy()] = long[column].to_numpy(dtype="float64")
        w = pd.DataFrame(arr, index=pd.DatetimeIndex(d_codes, name="Date"), columns=list(sym.cat.categories))
        w.columns.name = None
        return w.sort_index()
    w = long.pivot(index="Date", columns="Symbol", values=column)
    w.index.name = "Date"
    w.columns.name = None
    return w.sort_index()


def is_clean_ratio(ratio: float) -> bool:
    """A split ratio a board would declare (2, 3/2, 1/10 ...). Yahoo writes a
    spin-off as a split by the price drop (DHR 1.319 for Fortive, 5 Jul 2016)."""
    if not np.isfinite(ratio) or ratio <= 0:
        return False
    return any(abs(r * k - round(r * k)) < 1e-3 and 1 <= round(r * k) <= 100
               for r in (ratio, 1.0 / ratio) for k in range(1, 11))


def spin_dividends(actions: pd.DataFrame) -> pd.Series:
    """Rows whose dividend is a spin-off Yahoo has ALSO written as a split on the
    same day: a dividend at least SPIN_YIELD of the price beside a split whose
    ratio no board would declare. The split already keeps the series continuous,
    so applying the dividend too books the spin-off twice (DHR +61% on 5 Jul 2016
    while the close moved +3.6%; checked against the CRSP-checked dataset
    Johnbrick123/sp500-data, 10 Nov 2026). Returns a boolean mask on ``actions``;
    the yield test is applied in adjusted_close, where the price is known."""
    split = actions["Split"].fillna(0).astype("float64")
    odd = (split > 0) & ~split.map(is_clean_ratio)
    return odd & (actions["Dividend"].fillna(0) > 0)


SPIN_YIELD = 0.02


def adjusted_close(close: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Total-return close: split-adjusted close scaled back by every later
    dividend, by the CRSP and S&P convention: the ex-date return is
    (close + dividend) / previous close - 1, so the factor on the ex-date is
    close / (close + dividend).

    Yahoo's factor, 1 - dividend / previous close, agrees for an ordinary
    dividend but not for a large one: KDP's $103.75 special on 10 Jul 2018
    (close 123.66 -> 22.19) is +1.8% for the holder and +11.5% by Yahoo's
    factor. Changed 10 Nov 2026 (docs/DATA_CORRECTNESS.md).

    A dividend whose ex-date is not a row of ``close`` is applied at the next
    row; one on the first row (no previous close) is ignored, and so is a
    spin-off Yahoo also wrote as a split (spin_dividends).
    """
    close = close.astype("float64")
    if actions is None or actions.empty:
        return close.copy()
    acts = actions[actions["Symbol"].isin(close.columns)]
    spin = spin_dividends(acts) if "Split" in acts else pd.Series(False, index=acts.index)
    div = acts[acts["Dividend"] > 0]
    spin = spin.loc[div.index].to_numpy()
    idx = close.index
    pos = idx.searchsorted(pd.to_datetime(div["Date"]).values)
    col = close.columns.get_indexer(div["Symbol"])
    ok = (pos > 0) & (pos < len(idx))
    pos, col, spin = pos[ok], col[ok], spin[ok]
    amount = div["Dividend"].to_numpy(dtype="float64")[ok]
    filled = close.ffill().to_numpy()
    prev, now = filled[pos - 1, col], filled[pos, col]
    good = np.isfinite(prev) & (prev > 0) & np.isfinite(now) & (now > 0) & (amount < prev)
    good &= ~(spin & (amount >= SPIN_YIELD * prev))
    f = np.ones(close.shape, dtype="float64")
    # Two dividends landing on one row multiply (np.multiply.at is unbuffered).
    np.multiply.at(f, (pos[good], col[good]), now[good] / (now[good] + amount[good]))
    factors = pd.DataFrame(f, index=idx, columns=close.columns)
    # Each row is scaled by the product of the factors strictly AFTER it.
    after = factors[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    return close * after
