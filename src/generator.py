"""Transactions with a KNOWN true elasticity and a deliberately confounded
discount mechanism.

The confounding is the whole point of this fixture. In observational B2B sales
data, discounts are not handed out at random: reps give them to accounts that
are already shrinking, in order to hold on to them. So low price and low volume
occur together for a reason that has nothing to do with price sensitivity, and
a naive regression of volume on price picks up that reason instead of the
causal effect - usually with the wrong sign.

Because the true elasticity is chosen here, an estimator can be SCORED rather
than admired.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

SEGMENTS = ("national_account", "regional", "trade_counter")

#: TRUE price elasticity per segment. Negative: higher price, lower volume.
TRUE_ELASTICITY: dict[str, float] = {
    "national_account": -1.8,
    "regional": -1.1,
    "trade_counter": -0.4,
}

PRODUCT_LINES = ("fasteners", "hydraulics", "abrasives", "safety")

#: Gross margin rate per line at list price. Mix shift between these is what
#: the bridge has to separate from genuine price erosion.
LIST_MARGIN: dict[str, float] = {
    "fasteners": 0.42,
    "hydraulics": 0.28,
    "abrasives": 0.35,
    "safety": 0.19,
}

LIST_PRICE: dict[str, float] = {
    "fasteners": 12.0, "hydraulics": 240.0, "abrasives": 30.0, "safety": 18.0,
}

REGIONS = ("north", "south", "east", "west")
#: One region's reps discount far more than the others. Volume-adjusted rate
#: detection has to find this without being fooled by customer mix.
HEAVY_DISCOUNT_REGION = "west"


@dataclass(frozen=True)
class Txn:
    year: int
    customer_id: str
    segment: str
    region: str
    rep: str
    line: str
    units: float
    list_price: float
    net_price: float
    #: The OBSERVABLE proxy for the confounder: how the account's demand was
    #: trending before the discount was set. A real analyst gets this from
    #: prior-period volumes, which is exactly what this represents.
    prior_trend: float

    @property
    def revenue(self) -> float:
        return self.units * self.net_price

    @property
    def cost(self) -> float:
        # Cost is a property of the product line, not of the price charged.
        return self.units * self.list_price * (1.0 - LIST_MARGIN[self.line])

    @property
    def margin(self) -> float:
        return self.revenue - self.cost


def generate(
    customers: int = 1_200, seed: int = 20260911,
) -> tuple[list[Txn], dict[str, float]]:
    rnd = random.Random(seed)
    txns: list[Txn] = []

    for c in range(customers):
        segment = rnd.choice(SEGMENTS)
        region = rnd.choice(REGIONS)
        rep = f"{region}_rep_{rnd.randrange(6):02d}"
        customer_id = f"C{c:05d}"

        # The confounder: an account-level demand trend, independent of price.
        # Negative means the account is shrinking for its own reasons.
        trend = rnd.gauss(0.0, 0.25)

        base_units = math.exp(rnd.gauss(4.0, 0.7))

        for year in (2025, 2026):
            for line in PRODUCT_LINES:
                if rnd.random() < 0.35:
                    continue

                list_price = LIST_PRICE[line]

                # THE CONFOUNDED ASSIGNMENT. A shrinking account attracts a
                # bigger discount - the rep is defending the relationship.
                defensive = max(0.0, -trend) * 0.45
                regional = 0.06 if region == HEAVY_DISCOUNT_REGION else 0.0
                noise = rnd.uniform(0.0, 0.05)
                year_drift = 0.015 if year == 2026 else 0.0
                discount = min(0.45, defensive + regional + noise + year_drift)
                net_price = list_price * (1.0 - discount)

                # TRUE causal response to price, plus the trend effect.
                elasticity = TRUE_ELASTICITY[segment]
                price_ratio = net_price / list_price
                units = (
                    base_units
                    * (price_ratio ** elasticity)
                    * math.exp(trend * (1.0 if year == 2026 else 0.0))
                    * math.exp(rnd.gauss(0.0, 0.15))
                )

                # A genuine mix shift: 2026 sells more low-margin safety stock.
                if year == 2026 and line == "safety":
                    units *= 1.55
                if year == 2026 and line == "fasteners":
                    units *= 0.80

                txns.append(Txn(
                    year=year, customer_id=customer_id, segment=segment,
                    region=region, rep=rep, line=line,
                    units=round(units, 3), list_price=list_price,
                    net_price=round(net_price, 4), prior_trend=round(trend, 4),
                ))

    ground_truth = {f"elasticity_{s}": TRUE_ELASTICITY[s] for s in SEGMENTS}
    ground_truth["heavy_discount_region"] = HEAVY_DISCOUNT_REGION
    return txns, ground_truth
