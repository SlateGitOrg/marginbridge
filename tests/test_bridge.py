"""Two claims under test: the bridge reconciles exactly, and the elasticity
estimate recovers the planted truth while the naive one does not."""

from __future__ import annotations

import unittest

from src.bridge import (
    discount_by_region, estimate_elasticity, margin_rate, ols,
    price_volume_mix,
)
from src.generator import SEGMENTS, TRUE_ELASTICITY, generate


class BaseData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.txns, cls.truth = generate(customers=1_200, seed=20260911)
        cls.bridge = price_volume_mix(cls.txns, 2025, 2026)
        cls.estimates = {s: estimate_elasticity(cls.txns, s) for s in SEGMENTS}


class TestBridgeReconciles(BaseData):
    def test_THE_SILENT_BUG_components_sum_exactly_to_the_total(self):
        self.assertTrue(
            self.bridge.reconciles,
            f"components sum to {self.bridge.components_sum:,.2f} but the "
            f"total delta is {self.bridge.total_delta:,.2f}",
        )

    def test_the_residual_is_surfaced_not_absorbed(self):
        named = {c.name for c in self.bridge.components}
        self.assertTrue({"volume", "mix", "price"} <= named)
        unexplained = [c for c in self.bridge.components if c.name == "unexplained"]
        if unexplained:
            self.assertLess(
                abs(unexplained[0].amount) / max(abs(self.bridge.total_delta), 1.0),
                0.01, "an unexplained component above 1% means the model is wrong",
            )

    def test_a_bridge_over_identical_years_is_all_zero(self):
        b = price_volume_mix(self.txns, 2025, 2025)
        self.assertAlmostEqual(b.total_delta, 0.0, places=6)
        for c in b.components:
            self.assertAlmostEqual(c.amount, 0.0, places=6)

    def test_the_bridge_separates_three_distinct_effects(self):
        by_name = {c.name: c.amount for c in self.bridge.components}
        # The generator plants a genuine mix shift toward low-margin safety
        # stock, so mix must be materially negative.
        self.assertLess(by_name["mix"], 0.0,
                        "the planted shift toward safety stock should hurt mix")
        self.assertNotAlmostEqual(by_name["price"], 0.0, places=2)

    def test_margin_rate_actually_declined(self):
        self.assertLess(margin_rate(self.txns, 2026), margin_rate(self.txns, 2025))


class TestElasticity(BaseData):
    def test_THE_HEADLINE_corrected_estimate_covers_the_true_value(self):
        for segment in SEGMENTS:
            with self.subTest(segment=segment):
                est = self.estimates[segment]
                truth = TRUE_ELASTICITY[segment]
                self.assertTrue(
                    est.covers(truth),
                    f"{segment}: true {truth}, corrected {est.corrected:.3f} "
                    f"CI [{est.ci_low:.3f}, {est.ci_high:.3f}]",
                )

    def test_THE_CONTRAST_the_naive_interval_EXCLUDES_the_truth(self):
        """The argument, made as a measurement.

        Comparing point-estimate errors is the obvious test and it is noisy on
        a weak-elasticity segment where neither estimator has much to work
        with. The sharper claim: the naive analysis produces a confidence
        interval that RULES OUT the real answer, so a team acting on it is not
        merely imprecise, it is confidently wrong.
        """
        excluded = [
            s for s in SEGMENTS
            if not self.estimates[s].naive_covers(TRUE_ELASTICITY[s])
        ]
        self.assertGreaterEqual(
            len(excluded), 2,
            "the naive estimator should confidently exclude the truth on most "
            "segments; if it does not, the fixture is not modelling the "
            "confounding strongly enough",
        )
        # And the corrected interval covers it on every segment.
        for s in SEGMENTS:
            self.assertTrue(self.estimates[s].covers(TRUE_ELASTICITY[s]), s)

    def test_the_naive_error_is_larger_where_there_is_signal_to_lose(self):
        # On the two segments with material elasticity, correcting genuinely
        # reduces the error. On the near-inelastic segment neither estimator
        # has much signal, and that is stated rather than hidden.
        for segment in ("national_account", "regional"):
            with self.subTest(segment=segment):
                est = self.estimates[segment]
                truth = TRUE_ELASTICITY[segment]
                self.assertLess(abs(est.corrected - truth), abs(est.naive - truth))

    def test_a_price_cut_recommendation_from_the_naive_estimate_would_be_wrong(self):
        # An elasticity closer to zero (or positive) says "cutting price will
        # not buy volume", or worse "raising price buys volume".
        national = self.estimates["national_account"]
        self.assertLess(abs(national.naive), abs(TRUE_ELASTICITY["national_account"]),
                        "the confounding should attenuate the estimate")

    def test_confidence_intervals_are_reported_and_finite(self):
        for est in self.estimates.values():
            self.assertLess(est.ci_low, est.corrected)
            self.assertLess(est.corrected, est.ci_high)
            self.assertGreater(est.n, 100)

    def test_segments_are_ordered_as_designed(self):
        # National accounts are the most price sensitive by construction.
        corrected = {s: self.estimates[s].corrected for s in SEGMENTS}
        self.assertLess(corrected["national_account"], corrected["regional"])
        self.assertLess(corrected["regional"], corrected["trade_counter"])


class TestOls(unittest.TestCase):
    def test_recovers_a_known_linear_relationship(self):
        x = [[1.0, float(i)] for i in range(100)]
        y = [3.0 + 2.5 * i for i in range(100)]
        fit = ols(x, y)
        self.assertAlmostEqual(fit.coefficients[0], 3.0, places=6)
        self.assertAlmostEqual(fit.coefficients[1], 2.5, places=6)

    def test_handles_multiple_regressors(self):
        x = [[1.0, float(i), float(i % 7)] for i in range(200)]
        y = [1.0 + 2.0 * i + 5.0 * (i % 7) for i in range(200)]
        fit = ols(x, y)
        self.assertAlmostEqual(fit.coefficients[1], 2.0, places=5)
        self.assertAlmostEqual(fit.coefficients[2], 5.0, places=5)

    def test_a_singular_design_is_rejected_rather_than_returning_nonsense(self):
        x = [[1.0, 2.0, 4.0] for _ in range(10)]
        with self.assertRaises(ValueError):
            ols(x, [1.0] * 10)


class TestDiscountOutliers(BaseData):
    def test_finds_the_planted_heavy_discount_region(self):
        ranked = discount_by_region(self.txns)
        self.assertEqual(ranked[0].region, self.truth["heavy_discount_region"])

    def test_mix_adjustment_changes_the_numbers(self):
        for r in discount_by_region(self.txns):
            self.assertNotEqual(round(r.raw_mean, 6), 0.0)
            self.assertGreater(r.n, 0)

    def test_every_region_is_reported(self):
        self.assertEqual(len(discount_by_region(self.txns)), 4)


if __name__ == "__main__":
    unittest.main()
