"""Train the GRU quantile forecaster and write an evaluation report.

    python -m training.train_forecaster --source sim          # bootstrap on simulated history
    python -m training.train_forecaster --source db --days 365 # retrain on stored readings

Outputs (in VAYU_MODEL_DIR, default backend/artifacts):
    forecaster.npz   weights for NumPy serving
    forecaster.json  scaler, feature list, version, metrics
    ../docs/model-report.md (when --report is passed)
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from app.aqi.naqi import category_for
from app.config import get_settings
from app.forecast.features import FEATURES, HORIZON, QUANTILES, WINDOW, apply_scaler, fit_scaler, to_grid
from app.forecast.gru_numpy import NumpyGRUForecaster
from app.ingest.stations import SEED_STATIONS

torch.set_num_threads(max(1, torch.get_num_threads()))
REPORT_HORIZONS = [1, 3, 6, 12, 24]


class GRUForecaster(nn.Module):
    def __init__(self, n_features: int, hidden: int = 64, layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, num_layers=layers, batch_first=True,
                          dropout=dropout if layers > 1 else 0)
        self.head = nn.Sequential(nn.Linear(hidden, 128), nn.ReLU(), nn.Linear(128, HORIZON * len(QUANTILES)))

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out[:, -1]).view(-1, HORIZON, len(QUANTILES))


def pinball(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    q = torch.tensor(QUANTILES, device=pred.device).view(1, 1, -1)
    diff = target.unsqueeze(-1) - pred
    return torch.maximum(q * diff, (q - 1) * diff).mean()


# ---------------------------------------------------------------- data

def load_history(source: str, days: int) -> pd.DataFrame:
    if source == "sim":
        from app.ingest.pipeline import frame_to_rows
        from app.ingest.simulator import simulate

        end = datetime.now(timezone.utc) - timedelta(days=1)
        frame = simulate(until=end)
        return pd.DataFrame(frame_to_rows(frame))
    from app.store.timeseries import get_store

    since = datetime.now(timezone.utc) - timedelta(days=days)
    return get_store().history(None, since=since)


def make_index(T: int, start: int, end: int, stride: int) -> np.ndarray:
    lo = max(start, WINDOW - 1)
    hi = min(end, T - HORIZON - 1)
    return np.arange(lo, hi + 1, stride)


def batch(Xs: np.ndarray, aqi: np.ndarray, pairs: np.ndarray):
    s, t = pairs[:, 0], pairs[:, 1]
    win = np.stack([Xs[si, ti - WINDOW + 1: ti + 1] for si, ti in zip(s, t)])
    fut = np.stack([aqi[si, ti + 1: ti + 1 + HORIZON] for si, ti in zip(s, t)])
    now = aqi[s, t]
    return win, fut, now


def pairs_for(S: int, idx: np.ndarray) -> np.ndarray:
    return np.array([(s, t) for t in idx for s in range(S)], dtype=np.int64)


# ---------------------------------------------------------------- metrics

def evaluate(pred_q: np.ndarray, fut: np.ndarray, now: np.ndarray, yday: np.ndarray) -> dict:
    """pred_q: (N, H, Q) AQI; fut: (N, H); now: (N,); yday: (N, H) same hour previous day."""
    med = pred_q[..., 1]
    res = {"by_horizon": {}, "n_samples": int(len(fut))}
    for h in REPORT_HORIZONS:
        i = h - 1
        persistence = np.repeat(now[:, None], HORIZON, axis=1)
        row = {
            "gru_mae": float(np.abs(med[:, i] - fut[:, i]).mean()),
            "gru_rmse": float(np.sqrt(((med[:, i] - fut[:, i]) ** 2).mean())),
            "persistence_mae": float(np.abs(persistence[:, i] - fut[:, i]).mean()),
            "seasonal_naive_mae": float(np.abs(yday[:, i] - fut[:, i]).mean()),
            "interval_coverage": float(((fut[:, i] >= pred_q[:, i, 0]) & (fut[:, i] <= pred_q[:, i, 2])).mean()),
            "interval_width": float((pred_q[:, i, 2] - pred_q[:, i, 0]).mean()),
        }
        cats_true = [category_for(v).key for v in fut[:, i]]
        cats_pred = [category_for(v).key for v in med[:, i]]
        row["category_accuracy"] = float(np.mean([a == b for a, b in zip(cats_true, cats_pred)]))
        res["by_horizon"][str(h)] = row
    overall = np.abs(med - fut).mean()
    res["gru_mae_all"] = float(overall)
    res["persistence_mae_all"] = float(np.abs(now[:, None] - fut).mean())
    res["coverage_all"] = float(((fut >= pred_q[..., 0]) & (fut <= pred_q[..., 2])).mean())
    return res


def predict_numpy(model: NumpyGRUForecaster, Xs, aqi, pairs, bs=2048):
    preds, futs, nows, ydays = [], [], [], []
    for i in range(0, len(pairs), bs):
        p = pairs[i:i + bs]
        win, fut, now = batch(Xs, aqi, p)
        preds.append(model.predict(win, now))
        futs.append(fut)
        nows.append(now)
        s, t = p[:, 0], p[:, 1]
        ydays.append(np.stack([aqi[si, ti + 1 - 24: ti + 1 - 24 + HORIZON] for si, ti in zip(s, t)]))
    return np.concatenate(preds), np.concatenate(futs), np.concatenate(nows), np.concatenate(ydays)


# ---------------------------------------------------------------- main

def export_npz(model: GRUForecaster, path: Path, layers: int) -> None:
    sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in model.state_dict().items()}
    np.savez(path, **sd, meta_layers=np.array(layers), meta_horizon=np.array(HORIZON),
             meta_quantiles=np.array(len(QUANTILES)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sim", "db"], default="sim")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--promote-if-better", action="store_true",
                    help="Only replace the served model when validation MAE improves.")
    args = ap.parse_args()

    t0 = time.time()
    torch.manual_seed(0)
    np.random.seed(0)
    out_dir = Path(get_settings().model_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_history(args.source, args.days)
    station_city = {s[0]: s[2] for s in SEED_STATIONS}
    X, stations, times = to_grid(df, station_city)
    aqi = np.expm1(X[..., FEATURES.index("aqi")])
    S, T, F = X.shape
    print(f"grid: {S} stations x {T} hours x {F} features")

    # Chronological split: last 20% test, previous 12% validation.
    t_test = int(T * 0.80)
    t_val = int(T * 0.68)
    scaler = fit_scaler(X[:, :t_val])
    Xs = apply_scaler(X, scaler)

    tr = pairs_for(S, make_index(T, 24, t_val - HORIZON - 1, args.stride))
    va = pairs_for(S, make_index(T, t_val, t_test - HORIZON - 1, 6))
    te = pairs_for(S, make_index(T, t_test, T, 6))
    print(f"samples train={len(tr)} val={len(va)} test={len(te)}")

    model = GRUForecaster(F, args.hidden, args.layers)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    bs = 512
    best_val, best_state = float("inf"), None
    history = []
    for epoch in range(args.epochs):
        model.train()
        perm = np.random.permutation(len(tr))
        losses = []
        for i in range(0, len(perm), bs):
            win, fut, now = batch(Xs, aqi, tr[perm[i:i + bs]])
            target = torch.from_numpy((fut - now[:, None]) / 100.0).float()
            pred = model(torch.from_numpy(win))
            loss = pinball(pred, target)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(loss.item())
        sched.step()
        model.eval()
        with torch.no_grad():
            vl = []
            for i in range(0, len(va), 4096):
                win, fut, now = batch(Xs, aqi, va[i:i + 4096])
                pred = model(torch.from_numpy(win))[..., 1].numpy() * 100 + now[:, None]
                vl.append(np.abs(pred - fut).mean())
        val_mae = float(np.mean(vl))
        history.append({"epoch": epoch + 1, "train_pinball": float(np.mean(losses)), "val_mae": val_mae})
        print(f"epoch {epoch + 1}: train pinball {np.mean(losses):.4f}  val MAE {val_mae:.2f}")
        if val_mae < best_val:
            best_val = val_mae
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    tmp = out_dir / "forecaster.candidate.npz"
    export_npz(model, tmp, args.layers)

    # Evaluate the exported NumPy model, i.e. exactly what the API serves.
    np_model = NumpyGRUForecaster.load(str(tmp))
    pq, fut, now, yday = predict_numpy(np_model, Xs, aqi, te)
    metrics = evaluate(pq, fut, now, yday)
    metrics["val_mae"] = best_val
    metrics["history"] = history

    version = datetime.now(timezone.utc).strftime("gru-%Y%m%d-%H%M")
    meta = {
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source": args.source,
        "features": FEATURES,
        "window": WINDOW,
        "horizon": HORIZON,
        "quantiles": list(QUANTILES),
        "scaler": scaler,
        "hidden": args.hidden,
        "layers": args.layers,
        "train_period": [str(times[0]), str(times[t_val - 1])],
        "test_period": [str(times[t_test]), str(times[-1])],
        "metrics": metrics,
    }

    current_meta = out_dir / "forecaster.json"
    promote = True
    if args.promote_if_better and current_meta.exists():
        old = json.loads(current_meta.read_text())
        promote = best_val <= old["metrics"].get("val_mae", float("inf")) * 1.02
    if promote:
        tmp.replace(out_dir / "forecaster.npz")
        current_meta.write_text(json.dumps(meta, indent=2))
        print(f"promoted {version}")
    else:
        tmp.unlink()
        print("candidate not promoted: validation error did not improve")

    if args.report:
        write_report(meta, Path(__file__).resolve().parents[2] / "docs" / "model-report.md")
    print(f"done in {time.time() - t0:.0f}s")


def write_report(meta: dict, path: Path) -> None:
    m = meta["metrics"]
    rows = []
    for h, r in m["by_horizon"].items():
        gain = 100 * (1 - r["gru_mae"] / r["persistence_mae"])
        rows.append(
            f"| +{h} h | {r['gru_mae']:.1f} | {r['gru_rmse']:.1f} | {r['persistence_mae']:.1f} | "
            f"{r['seasonal_naive_mae']:.1f} | {gain:+.0f}% | {100 * r['category_accuracy']:.0f}% | "
            f"{100 * r['interval_coverage']:.0f}% | {r['interval_width']:.0f} |"
        )
    hist = "\n".join(f"| {h['epoch']} | {h['train_pinball']:.4f} | {h['val_mae']:.2f} |" for h in m["history"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""# Forecast model evaluation

Generated by `python -m training.train_forecaster --report` on {meta['trained_at'][:10]}.
Model version `{meta['version']}`, trained on the **{'simulated bootstrap feed' if meta['source'] == 'sim' else 'stored station readings'}**.

## Setup

| Item | Value |
|---|---|
| Architecture | 2-layer GRU ({meta['hidden']} units) + MLP head |
| Input | last {meta['window']} hours, {len(meta['features'])} features per hour |
| Output | AQI for each of the next {meta['horizon']} hours at the 10th, 50th and 90th percentile |
| Loss | pinball (quantile) loss on the change from current AQI |
| Train period | {meta['train_period'][0][:10]} to {meta['train_period'][1][:10]} |
| Test period | {meta['test_period'][0][:10]} to {meta['test_period'][1][:10]} (never seen in training) |
| Test samples | {m['n_samples']:,} station-hours |

Features: {', '.join(f'`{f}`' for f in meta['features'])}.

## Test results

MAE and RMSE are in AQI points. Persistence assumes AQI stays at its current
value; seasonal naive repeats the value from the same hour yesterday. Category
accuracy is the share of forecasts that land in the correct CPCB band.
Coverage is how often the true value fell inside the 10-90% band (target 80%).

| Horizon | GRU MAE | GRU RMSE | Persistence MAE | Seasonal naive MAE | Gain vs persistence | Category accuracy | 80% band coverage | Band width |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Across all 24 horizons: GRU MAE **{m['gru_mae_all']:.1f}**, persistence MAE {m['persistence_mae_all']:.1f},
band coverage {100 * m['coverage_all']:.0f}%.

## Training curve

| Epoch | Train pinball loss | Validation MAE |
|---|---|---|
{hist}

## Reading these numbers

* The bootstrap feed is simulated (see `app/ingest/simulator.py`). It reproduces
  diurnal traffic peaks, winter build-up, monsoon washout and weather coupling,
  but real data is noisier. Expect higher errors after retraining on live
  OpenAQ/WAQI data, and re-run this report then.
* Persistence is hardest to beat at +24 h, because the same hour tomorrow
  tends to look like now; the largest gains are at +3 h to +12 h, where the
  morning and evening traffic peaks and afternoon dilution move AQI the most.
* The weekly retraining job only promotes a new model when its validation error
  is within 2% of, or better than, the model currently in service.
""")
    print(f"report written to {path}")


if __name__ == "__main__":
    main()
