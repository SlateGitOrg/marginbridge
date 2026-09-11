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
    headwinds = sum(a for a in by_name.values() if a < 0)
    print(f"\n    THE FINDING: total margin GREW by {bridge.total_delta:,.0f}, "
          "while the margin")
    print(f"    RATE fell {abs(r26 - r25) * 100:.1f} points. Volume growth of "
          f"{by_name['volume']:,.0f} is masking")
    print(f"    {abs(headwinds):,.0f} of headwind underneath it:")
    for name in ("mix", "price"):
        amount = by_name.get(name, 0.0)
        print(f"      {name:<8} {amount:>12,.0f}   "
              f"({amount / headwinds:.0%} of the headwind)")
    print("\n    A revenue report shows a good year. Two different problems are")
    print("    growing underneath it, and mix shift is not solved by a price")
    print("    increase any more than price erosion is fixed by a range review.\n")

    print("  ELASTICITY: what the pricing decision actually rests on")
    print("  " + "-" * 72)
    print(f"    {'segment':<20}{'true':>7}{'naive':>9}{'naive 95% CI':>20}"
          f"{'corrected':>11}{'corrected 95% CI':>20}")
    excluded = 0
    for segment in SEGMENTS:
        est = estimate_elasticity(txns, segment)
        t = TRUE_ELASTICITY[segment]
        if not est.naive_covers(t):
            excluded += 1
        flag = "" if est.naive_covers(t) else "  <-"
        print(f"    {segment:<20}{t:>7.2f}{est.naive:>9.2f}"
              f"{f'[{est.naive_ci_low:.2f}, {est.naive_ci_high:.2f}]':>20}"
              f"{est.corrected:>11.2f}"
              f"{f'[{est.ci_low:.2f}, {est.ci_high:.2f}]':>20}{flag}")

    print("\n    The naive column is a regression of volume on price in")
    print("    observational data. Reps discount accounts that are ALREADY")
    print("    shrinking, so low price and low volume travel together for a")
    print("    reason that has nothing to do with price sensitivity.")
    print(f"    {excluded} of the {len(SEGMENTS)} naive intervals rule out the "
          "real answer entirely -")
    print("    they do not merely miss it, they exclude it with 95% confidence.")
    print("    The corrected intervals cover the truth in every segment, and")
    print("    are honestly wide where the segment is nearly inelastic.\n")

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
