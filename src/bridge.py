"""The price-volume-mix bridge, and the elasticity estimate.

THE DIFFERENTIATOR LIVES HERE (twice).

1. THE BRIDGE. "Margin fell 2.3 points" is one number covering three unrelated
   problems with three different responses: price erosion, mix shift toward
   lower-margin lines, and discount-policy drift. The decomposition separates
   them - and it MUST sum exactly to the total, because a bridge whose
   components do not reconcile is the classic silent error that invalidates the
   whole analysis while looking entirely reasonable.

2. THE ELASTICITY. A naive regression of volume on price in observational data
   estimates the confounder, not the causal effect. Discounts go to accounts
   that are already shrinking, so low price and low volume travel together and
   the fitted coefficient comes out attenuated or positive. Acting on it means
   cutting price to chase volume that was never price-driven.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .generator import LIST_MARGIN, Txn


# ---------------------------------------------------------------------------
# Ordinary least squares, via normal equations. No third-party dependencies.
# ---------------------------------------------------------------------------

def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(matrix)
    aug = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular design matrix")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col] / aug[col][col]
            for k in range(col, n + 1):
                aug[r][k] -= factor * aug[col][k]
    return [aug[i][n] / aug[i][i] for i in range(n)]


@dataclass(frozen=True)
class Fit:
    coefficients: list[float]
    standard_errors: list[float]
    n: int

    def ci(self, index: int, z: float = 1.96) -> tuple[float, float]:
        c, se = self.coefficients[index], self.standard_errors[index]
        return (c - z * se, c + z * se)


def ols(x_rows: list[list[float]], y: list[float]) -> Fit:
    """x_rows must already include an intercept column."""
    k = len(x_rows[0])
    n = len(x_rows)
    xtx = [[sum(r[i] * r[j] for r in x_rows) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * yv for r, yv in zip(x_rows, y)) for i in range(k)]
    beta = _solve(xtx, xty)

    residuals = [
        yv - sum(b * xv for b, xv in zip(beta, row))
        for row, yv in zip(x_rows, y)
    ]
    dof = max(1, n - k)
    sigma2 = sum(r * r for r in residuals) / dof
    inv = _invert(xtx)
    ses = [math.sqrt(max(0.0, sigma2 * inv[i][i])) for i in range(k)]
    return Fit(beta, ses, n)


def _invert(m: list[list[float]]) -> list[list[float]]:
    n = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)]
           for i, row in enumerate(m)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        if abs(p) < 1e-12:
            raise ValueError("singular matrix")
        aug[col] = [v / p for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col]
            aug[r] = [v - f * w for v, w in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


# ---------------------------------------------------------------------------
# Elasticity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ElasticityEstimate:
    segment: str
    naive: float
    naive_ci_low: float
    naive_ci_high: float
    corrected: float
    ci_low: float
    ci_high: float
    n: int

    def covers(self, truth: float) -> bool:
        return self.ci_low <= truth <= self.ci_high

    def naive_covers(self, truth: float) -> bool:
        """Does the NAIVE interval contain the true value?

        This is the sharper question. Comparing point-estimate errors is noisy
        on a weak-elasticity segment, where neither estimator has much signal.
        Whether the interval EXCLUDES the truth is the statement that matters:
        it means the naive analysis would confidently rule out the real answer.
        """
        return self.naive_ci_low <= truth <= self.naive_ci_high


def estimate_elasticity(
    txns: list[Txn], segment: str,
) -> ElasticityEstimate:
    rows = [t for t in txns if t.segment == segment]

    # NAIVE: log(units) ~ a + b*log(price). b is read as the elasticity, and
    # it is contaminated by the discount-assignment mechanism.
    x_naive = [[1.0, math.log(t.net_price)] for t in rows]
    y = [math.log(t.units) for t in rows]
    naive_fit = ols(x_naive, y)
    naive = naive_fit.coefficients[1]
    naive_low, naive_high = naive_fit.ci(1)

    # CORRECTED: control for the confounder (the account's prior demand trend)
    # and for the product line, whose base volumes differ by orders of
    # magnitude. Omitting the line would load that variation onto price.
    lines = sorted({t.line for t in rows})
    x_corrected: list[list[float]] = []
    for t in rows:
        row = [1.0, math.log(t.net_price / t.list_price), t.prior_trend]
        # Dummy-code the line, dropping the first to avoid collinearity.
        row.extend(1.0 if t.line == ln else 0.0 for ln in lines[1:])
        x_corrected.append(row)

    fit = ols(x_corrected, y)
    low, high = fit.ci(1)
    return ElasticityEstimate(
        segment=segment, naive=naive,
        naive_ci_low=naive_low, naive_ci_high=naive_high,
        corrected=fit.coefficients[1],
        ci_low=low, ci_high=high, n=len(rows),
    )


# ---------------------------------------------------------------------------
# Price / volume / mix bridge
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BridgeComponent:
    name: str
    amount: float


@dataclass(frozen=True)
class Bridge:
    base_margin: float
    final_margin: float
    components: list[BridgeComponent]

    @property
    def total_delta(self) -> float:
        return self.final_margin - self.base_margin

    @property
    def components_sum(self) -> float:
        return sum(c.amount for c in self.components)

    @property
    def reconciles(self) -> bool:
        # Tolerance is absolute and tight. A bridge that "nearly" reconciles is
        # a bridge with a bug in it.
        return abs(self.components_sum - self.total_delta) < 1e-6


def _by_line(txns: list[Txn], year: int) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for t in txns:
        if t.year != year:
            continue
        d = out.setdefault(t.line, {"units": 0.0, "revenue": 0.0, "cost": 0.0})
        d["units"] += t.units
        d["revenue"] += t.revenue
        d["cost"] += t.cost
    return out


def price_volume_mix(txns: list[Txn], base_year: int, final_year: int) -> Bridge:
    """Decompose the margin movement into price, volume and mix.

    Definitions, stated explicitly because every organisation defines these
    slightly differently and an undefined bridge is unarguable:

      volume  - change in total units, holding the base-year mix and the
                base-year per-unit margin
      mix     - change in the SHARE of each line, at base-year per-unit margin,
                applied to final-year total units
      price   - change in per-unit margin (net price movement), applied to
                final-year units and mix
    """
    base = _by_line(txns, base_year)
    final = _by_line(txns, final_year)
    lines = sorted(set(base) | set(final))

    base_units = sum(base.get(ln, {}).get("units", 0.0) for ln in lines)
    final_units = sum(final.get(ln, {}).get("units", 0.0) for ln in lines)

    base_margin_total = sum(
        base.get(ln, {}).get("revenue", 0.0) - base.get(ln, {}).get("cost", 0.0)
        for ln in lines
    )
    final_margin_total = sum(
        final.get(ln, {}).get("revenue", 0.0) - final.get(ln, {}).get("cost", 0.0)
        for ln in lines
    )

    def unit_margin(d: dict[str, dict[str, float]], ln: str) -> float:
        row = d.get(ln)
        if not row or row["units"] == 0:
            return 0.0
        return (row["revenue"] - row["cost"]) / row["units"]

    def share(d: dict[str, dict[str, float]], ln: str, total: float) -> float:
        if total == 0:
            return 0.0
        return d.get(ln, {}).get("units", 0.0) / total

    volume = sum(
        (final_units - base_units) * share(base, ln, base_units)
        * unit_margin(base, ln)
        for ln in lines
    )
    mix = sum(
        final_units * (share(final, ln, final_units) - share(base, ln, base_units))
        * unit_margin(base, ln)
        for ln in lines
    )
    price = sum(
        final_units * share(final, ln, final_units)
        * (unit_margin(final, ln) - unit_margin(base, ln))
        for ln in lines
    )

    components = [
        BridgeComponent("volume", volume),
        BridgeComponent("mix", mix),
        BridgeComponent("price", price),
    ]
    # Any arithmetic residue is surfaced as its own component rather than
    # quietly absorbed into one of the three.
    residual = (final_margin_total - base_margin_total) - sum(
        c.amount for c in components)
    if abs(residual) > 1e-9:
        components.append(BridgeComponent("unexplained", residual))

    return Bridge(base_margin_total, final_margin_total, components)


def margin_rate(txns: list[Txn], year: int) -> float:
    rows = [t for t in txns if t.year == year]
    revenue = sum(t.revenue for t in rows)
    return sum(t.margin for t in rows) / revenue if revenue else 0.0


# ---------------------------------------------------------------------------
# Discount outliers, adjusted for customer mix
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegionDiscount:
    region: str
    raw_mean: float
    #: Mean discount after re-weighting to the company-wide segment mix, so a
    #: region is not penalised for serving more price-sensitive customers.
    mix_adjusted: float
    n: int


def discount_by_region(txns: list[Txn]) -> list[RegionDiscount]:
    company_mix: dict[str, float] = {}
    for t in txns:
        company_mix[t.segment] = company_mix.get(t.segment, 0.0) + 1
    total = sum(company_mix.values())
    for k in company_mix:
        company_mix[k] /= total

    regions = sorted({t.region for t in txns})
    out: list[RegionDiscount] = []
    for region in regions:
        rows = [t for t in txns if t.region == region]
        raw = sum(1.0 - t.net_price / t.list_price for t in rows) / len(rows)

        adjusted = 0.0
        for segment, weight in company_mix.items():
            seg_rows = [t for t in rows if t.segment == segment]
            if not seg_rows:
                continue
            seg_mean = sum(
                1.0 - t.net_price / t.list_price for t in seg_rows) / len(seg_rows)
            adjusted += weight * seg_mean
        out.append(RegionDiscount(region, raw, adjusted, len(rows)))
    return sorted(out, key=lambda r: -r.mix_adjusted)
