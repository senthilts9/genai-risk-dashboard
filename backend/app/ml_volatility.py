"""
ML-based volatility forecasting.

This is trained live, on-demand, every time the endpoint is called -- there
is no pre-trained pickle sitting on disk going stale. The dataset is small
(a year of daily returns is ~250 rows) so a GradientBoostingRegressor trains
in milliseconds, which makes "train live per request" a legitimate choice
here rather than a shortcut.

Honesty is the point of this module: it reports test-set R^2/RMSE against a
naive baseline (yesterday's realized vol as today's forecast), not just a
raw metric in isolation. A model that doesn't beat the naive baseline is
reported as such -- that's a real, useful finding, not a failure to hide.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error

TRADING_DAYS = 252
FORWARD_WINDOW = 5   # predict realized vol over the next 5 trading days
FEATURE_WINDOW = 20  # longest lookback used in feature engineering


def _build_feature_frame(returns: pd.Series) -> pd.DataFrame:
    r = returns.reset_index(drop=True)
    df = pd.DataFrame({"ret": r})
    df["lag1_ret"] = df["ret"].shift(1)
    df["lag1_abs_ret"] = df["lag1_ret"].abs()
    df["vol_5"] = df["ret"].rolling(5).std() * np.sqrt(TRADING_DAYS)
    df["vol_10"] = df["ret"].rolling(10).std() * np.sqrt(TRADING_DAYS)
    df["vol_20"] = df["ret"].rolling(20).std() * np.sqrt(TRADING_DAYS)
    df["skew_20"] = df["ret"].rolling(20).skew()
    df["kurt_20"] = df["ret"].rolling(20).kurt()
    # EWMA vol (lambda=0.94), annualized
    lam = 0.94
    ewma_var = np.zeros(len(df))
    ewma_var[0] = df["ret"].iloc[0] ** 2 if not pd.isna(df["ret"].iloc[0]) else 0
    ret_vals = df["ret"].fillna(0).values
    for i in range(1, len(df)):
        ewma_var[i] = lam * ewma_var[i - 1] + (1 - lam) * ret_vals[i - 1] ** 2
    df["ewma_vol"] = np.sqrt(ewma_var * TRADING_DAYS)

    # Target: realized vol over the NEXT `FORWARD_WINDOW` days (shifted back so
    # each row's target is knowable only using future data during training,
    # and is NaN / dropped for the most recent rows where the future isn't observed yet)
    fwd_vol = df["ret"].shift(-1).rolling(FORWARD_WINDOW).std().shift(-(FORWARD_WINDOW - 1)) * np.sqrt(TRADING_DAYS)
    df["target_fwd_vol"] = fwd_vol
    return df


FEATURE_COLS = ["lag1_ret", "lag1_abs_ret", "vol_5", "vol_10", "vol_20", "skew_20", "kurt_20", "ewma_vol"]


def train_and_forecast(returns: pd.Series) -> dict:
    df = _build_feature_frame(returns)

    # Rows usable for supervised training: need full feature history AND a known forward target
    trainable = df.dropna(subset=FEATURE_COLS + ["target_fwd_vol"]).reset_index(drop=True)
    if len(trainable) < 30:
        return {"error": "Not enough history to train (need at least ~30 usable rows after feature/target windows)."}

    split = int(len(trainable) * 0.8)
    X_train, X_test = trainable[FEATURE_COLS].iloc[:split], trainable[FEATURE_COLS].iloc[split:]
    y_train, y_test = trainable["target_fwd_vol"].iloc[:split], trainable["target_fwd_vol"].iloc[split:]

    model = GradientBoostingRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    r2 = r2_score(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))

    # Naive baseline: "tomorrow's forward vol = today's trailing 5-day vol"
    naive_preds = X_test["vol_5"].values
    naive_rmse = np.sqrt(mean_squared_error(y_test, naive_preds))
    naive_r2 = r2_score(y_test, naive_preds)

    beats_baseline = rmse < naive_rmse

    importances = dict(zip(FEATURE_COLS, model.feature_importances_.round(4).tolist()))
    importances = dict(sorted(importances.items(), key=lambda kv: -kv[1]))

    # Live forecast: most recent row with full features but no forward target yet
    latest_features = df.dropna(subset=FEATURE_COLS)[FEATURE_COLS].iloc[[-1]]
    live_forecast = float(model.predict(latest_features)[0])

    return {
        "live_forecast_annualized_vol": round(live_forecast, 4),
        "model": "GradientBoostingRegressor",
        "forward_window_days": FORWARD_WINDOW,
        "train_rows": int(split), "test_rows": int(len(trainable) - split),
        "test_r2": round(float(r2), 4),
        "test_rmse": round(float(rmse), 5),
        "naive_baseline_r2": round(float(naive_r2), 4),
        "naive_baseline_rmse": round(float(naive_rmse), 5),
        "beats_naive_baseline": bool(beats_baseline),
        "improvement_vs_naive_pct": round((naive_rmse - rmse) / naive_rmse * 100, 2) if naive_rmse > 0 else None,
        "feature_importances": importances,
    }
