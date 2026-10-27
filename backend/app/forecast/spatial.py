"""Estimate AQI at arbitrary points from station values.

* IDW: inverse distance weighting, power 2. Robust with few stations.
* Ordinary kriging: fits an exponential variogram to the current station field
  and solves the kriging system. Better when stations are dense and the field is
  smooth, and it returns an estimation variance that we fold into the
  forecast uncertainty band.

`interpolate` picks kriging when there are at least 6 nearby stations and the
variogram fit is sane, otherwise falls back to IDW.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EARTH_KM = 6371.0
SEARCH_RADIUS_KM = 45.0


def haversine_matrix(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2[None, :] - lat1[:, None]
    dlon = lon2[None, :] - lon1[:, None]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1)[:, None] * np.cos(lat2)[None, :] * np.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


@dataclass
class Estimate:
    value: np.ndarray       # (P,) or (P, K) if values had a trailing dim
    std: np.ndarray | None  # kriging standard deviation, (P,)
    method: str
    nearest_km: np.ndarray  # distance to nearest station, (P,)


def idw(dist: np.ndarray, values: np.ndarray, power: float = 2.0) -> np.ndarray:
    """dist: (P, S) km, values: (S,) or (S, K)."""
    d = np.maximum(dist, 0.05)
    w = 1.0 / d**power
    w = w / w.sum(axis=1, keepdims=True)
    return w @ values


def _exp_variogram(h, nugget, sill, rng):
    return nugget + sill * (1 - np.exp(-3 * h / rng))


def fit_variogram(dist: np.ndarray, z: np.ndarray) -> tuple[float, float, float] | None:
    iu = np.triu_indices(len(z), k=1)
    h = dist[iu]
    g = 0.5 * (z[iu[0]] - z[iu[1]]) ** 2
    if len(h) < 10 or np.var(z) < 1e-6:
        return None
    # Coarse grid search: robust and dependency-free.
    best, best_err = None, np.inf
    total = np.var(z)
    for rng in np.linspace(max(h.min(), 1.0), max(h.max(), 2.0) * 1.5, 25):
        for nug_frac in (0.0, 0.1, 0.2, 0.35):
            nugget = nug_frac * total
            sill = total - nugget
            err = np.mean((_exp_variogram(h, nugget, sill, rng) - g) ** 2)
            if err < best_err:
                best, best_err = (nugget, sill, rng), err
    return best


def ordinary_kriging(d_ss: np.ndarray, d_ps: np.ndarray, z: np.ndarray, params) -> tuple[np.ndarray, np.ndarray]:
    """z may be (S,) or (S, K); the same weights apply to every column."""
    nugget, sill, rng = params
    S = len(z)
    gamma = _exp_variogram(d_ss, nugget, sill, rng)
    np.fill_diagonal(gamma, 0.0)
    A = np.ones((S + 1, S + 1))
    A[:S, :S] = gamma
    A[S, S] = 0.0
    b = np.ones((d_ps.shape[0], S + 1))
    b[:, :S] = _exp_variogram(d_ps, nugget, sill, rng)
    sol = np.linalg.solve(A, b.T).T  # (P, S+1)
    w, mu = sol[:, :S], sol[:, S]
    est = w @ z
    var = np.maximum((w * b[:, :S]).sum(axis=1) + mu, 0)
    return est, np.sqrt(var)


def interpolate(points_lat, points_lon, st_lat, st_lon, values, method: str = "auto") -> Estimate:
    """values: (S,) current field, or (S, K) e.g. a 24-hour forecast per station.

    Kriging weights are fit on the first column and reused for all K columns;
    the spatial structure changes far more slowly than the values themselves.
    """
    values = np.asarray(values, dtype=float)
    d_ps = haversine_matrix(points_lat, points_lon, st_lat, st_lon)
    nearest = d_ps.min(axis=1)

    values_2d = values if values.ndim == 2 else values[:, None]
    out = np.zeros((d_ps.shape[0], values_2d.shape[1]))
    std = np.full(d_ps.shape[0], np.nan)
    methods = set()

    # Each point only sees stations within the search radius (or its 3 closest),
    # so a Delhi point is never influenced by Bengaluru. Points that share the
    # same station set are solved together.
    masks = d_ps <= SEARCH_RADIUS_KM
    for p in np.where(~masks.any(axis=1))[0]:
        masks[p, np.argsort(d_ps[p])[:3]] = True
    groups: dict[bytes, list[int]] = {}
    for p in range(d_ps.shape[0]):
        groups.setdefault(masks[p].tobytes(), []).append(p)

    st_lat, st_lon = np.asarray(st_lat, dtype=float), np.asarray(st_lon, dtype=float)
    for key, idx in groups.items():
        used = np.frombuffer(key, dtype=bool)
        d_pu = d_ps[np.ix_(idx, np.where(used)[0])]
        vals_u = values_2d[used]
        done = False
        if method in ("auto", "kriging") and used.sum() >= 6:
            d_ss = haversine_matrix(st_lat[used], st_lon[used], st_lat[used], st_lon[used])
            params = fit_variogram(d_ss, vals_u[:, 0])
            if params is not None:
                try:
                    est, sd = ordinary_kriging(d_ss, d_pu, vals_u, params)
                    # Kriging can overshoot with negative weights; keep inside the observed range.
                    out[idx] = np.clip(est, vals_u.min(axis=0), vals_u.max(axis=0))
                    std[idx] = sd
                    methods.add("kriging")
                    done = True
                except np.linalg.LinAlgError:
                    pass
        if not done:
            out[idx] = idw(d_pu, vals_u)
            methods.add("idw")

    value = out if values.ndim == 2 else out[:, 0]
    method_name = methods.pop() if len(methods) == 1 else "mixed"
    return Estimate(value, None if np.isnan(std).all() else np.nan_to_num(std), method_name, nearest)
