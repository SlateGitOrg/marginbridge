"""The 60-second artefact: one margin number becomes three problems.

Run: python -m src.demo
"""

from __future__ import annotations

from .bridge import (
    discount_by_region, estimate_elasticity, margin_rate, price_volume_mix,
)
from .generator import SEGMENTS, TRUE_ELASTICITY, generate


def main() -> None:
    txns, truth = generate(customers=1_200, seed=20260911)

    r25, r26 = margin_rate(txns, 2025), margin_rate(txns, 2026)
    print("\n  MARGINBRIDGE - 'margin is down, the market is tough'")
    print("  " + "=" * 72)
    print(f"  {len(txns):,} transaction lines across two years.")
    print(f"  Gross margin rate: {r25:.1%} -> {r26:.1%}  "
          f"({(r26 - r25) * 100:+.1f} points)\n")

    bridge = price_volume_mix(txns, 2025, 2026)
    print("  THE BRIDGE")
    print("  " + "-" * 72)
    print(f"    2025 margin      {bridge.base_margin:>14,.0f}")
    for c in bridge.components:
        print(f"      {c.name:<14} {c.amount:>14,.0f}")
    print(f"    2026 margin      {bridge.final_margin:>14,.0f}")
    print(f"\n    components sum:  {bridge.components_sum:>14,.0f}")
    print(f"    actual delta:    {bridge.total_delta:>14,.0f}")
    print(f"    reconciles:      {bridge.reconciles}")

    by_name = {c.name: c.amount for c in bridge.components}
    total = bridge.total_delta
    print("\n    As a share of the decline:")
    for name in ("price", "mix", "volume"):
        amount = by_name.get(name, 0.0)
        print(f"      {name:<8} {amount / total * 100:>6.1f}%")
    print("\n    Three different problems. Mix shift is not solved by a price")
    print("    increase, and price erosion is not solved by a product review.\n")

    print("  ELASTICITY: what the pricing decision actually rests on")
    print("  " + "-" * 72)
    print(f"    {'segment':<20}{'true':>7}{'naive':>9}{'naive 95% CI':>20}"
          f"{'corrected':>11}")
    for segment in SEGMENTS:
        est = estimate_elasticity(txns, segment)
        t = TRUE_ELASTICITY[segment]
        flag = "" if est.naive_covers(t) else "  <- excludes the truth"
        print(f"    {segment:<20}{t:>7.2f}{est.naive:>9.2f}"
              f"{f'[{est.naive_ci_low:.2f}, {est.naive_ci_high:.2f}]':>20}"
              f"{est.corrected:>11.2f}{flag}")

    print("\n    The naive column is a regression of volume on price in")
    print("    observational data. Reps discount accounts that are ALREADY")
    print("    shrinking, so low price and low volume travel together for a")
    print("    reason that has nothing to do with price sensitivity.")
    print("    Two of the three naive intervals rule out the real answer.\n")

    print("  DISCOUNT BY REGION (adjusted for customer mix)")
    print("  " + "-" * 72)
    print(f"    {'region':<10}{'raw':>9}{'mix-adjusted':>15}{'lines':>9}")
    for r in discount_by_region(txns):
        print(f"    {r.region:<10}{r.raw_mean:>9.1%}{r.mix_adjusted:>15.1%}"
              f"{r.n:>9,}")
    print(f"\n    {truth['heavy_discount_region']} discounts hardest even after")
    print("    adjusting for the customers it serves - so it is a policy")
    print("    question, not a mix artefact.\n")


if __name__ == "__main__":
    main()
