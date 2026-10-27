"""Dependency-free GRU inference.

The model is trained in PyTorch (see training/train_forecaster.py) and exported
to a .npz file. Serving it with NumPy keeps the API image small (no 700 MB
torch wheel) and starts in milliseconds. The equations match torch.nn.GRU:

    r = sigmoid(W_ir x + b_ir + W_hr h + b_hr)
    z = sigmoid(W_iz x + b_iz + W_hz h + b_hz)
    n = tanh(W_in x + b_in + r * (W_hn h + b_hn))
    h = (1 - z) * n + z * h
"""

from __future__ import annotations

import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class NumpyGRUForecaster:
    def __init__(self, weights: dict[str, np.ndarray], n_layers: int, horizon: int, n_quantiles: int):
        self.w = weights
        self.n_layers = n_layers
        self.horizon = horizon
        self.n_quantiles = n_quantiles

    @classmethod
    def load(cls, path: str) -> "NumpyGRUForecaster":
        data = np.load(path, allow_pickle=False)
        w = {k: data[k] for k in data.files if not k.startswith("meta_")}
        return cls(w, int(data["meta_layers"]), int(data["meta_horizon"]), int(data["meta_quantiles"]))

    def _layer(self, x: np.ndarray, layer: int) -> np.ndarray:
        W_ih = self.w[f"gru.weight_ih_l{layer}"]
        W_hh = self.w[f"gru.weight_hh_l{layer}"]
        b_ih = self.w[f"gru.bias_ih_l{layer}"]
        b_hh = self.w[f"gru.bias_hh_l{layer}"]
        H = W_hh.shape[1]
        B, T, _ = x.shape
        h = np.zeros((B, H), dtype=np.float32)
        gi_all = x @ W_ih.T + b_ih  # (B, T, 3H) computed once for all steps
        outs = np.empty((B, T, H), dtype=np.float32)
        for t in range(T):
            gi = gi_all[:, t]
            gh = h @ W_hh.T + b_hh
            r = _sigmoid(gi[:, :H] + gh[:, :H])
            z = _sigmoid(gi[:, H:2 * H] + gh[:, H:2 * H])
            n = np.tanh(gi[:, 2 * H:] + r * gh[:, 2 * H:])
            h = (1 - z) * n + z * h
            outs[:, t] = h
        return outs

    def predict(self, x: np.ndarray, current_aqi: np.ndarray) -> np.ndarray:
        """x: (B, WINDOW, F) scaled features, current_aqi: (B,) latest AQI.

        The network predicts the change from the current AQI (in AQI/100 units),
        which is easier to learn than absolute levels. Returns AQI, (B, HORIZON, Q).
        """
        h = x.astype(np.float32)
        for layer in range(self.n_layers):
            h = self._layer(h, layer)
        last = h[:, -1]
        z = np.maximum(0, last @ self.w["head.0.weight"].T + self.w["head.0.bias"])
        out = z @ self.w["head.2.weight"].T + self.w["head.2.bias"]
        out = out.reshape(-1, self.horizon, self.n_quantiles)
        # Quantile crossing guard: enforce q10 <= q50 <= q90.
        out = np.sort(out, axis=-1)
        aqi = current_aqi.reshape(-1, 1, 1) + out * 100.0
        return np.clip(aqi, 0, 500)
