"""The NumPy GRU must reproduce PyTorch exactly, or the served model differs from the evaluated one."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")


def test_numpy_gru_matches_torch(tmp_path):
    from app.forecast.features import FEATURES, HORIZON, WINDOW
    from app.forecast.gru_numpy import NumpyGRUForecaster
    from training.train_forecaster import GRUForecaster, export_npz

    torch.manual_seed(3)
    m = GRUForecaster(len(FEATURES), hidden=16, layers=2).eval()
    path = tmp_path / "m.npz"
    export_npz(m, path, layers=2)
    x = np.random.default_rng(0).normal(size=(5, WINDOW, len(FEATURES))).astype(np.float32)
    now = np.array([50, 120, 200, 80, 300], dtype=np.float32)

    with torch.no_grad():
        ref = np.sort(m(torch.from_numpy(x)).numpy(), axis=-1) * 100 + now[:, None, None]
    got = NumpyGRUForecaster.load(str(path)).predict(x, now)
    assert got.shape == (5, HORIZON, 3)
    assert np.allclose(got, np.clip(ref, 0, 500), atol=1e-3)


def test_simulator_is_deterministic():
    from datetime import datetime, timezone

    from app.ingest.simulator import simulate

    a = simulate(datetime(2024, 1, 5, tzinfo=timezone.utc), since=datetime(2024, 1, 4, tzinfo=timezone.utc))
    b = simulate(datetime(2024, 1, 5, tzinfo=timezone.utc), since=datetime(2024, 1, 4, tzinfo=timezone.utc))
    assert np.array_equal(a.pm25, b.pm25)
    assert a.pm25.min() > 0
