# marginbridge

> A price-volume-mix bridge plus elasticity estimated against the confounder, so the pricing recommendation is not backwards.

`FLAGSHIP` · **Business Analyst** · Expert · ~5-6 weeks · Manufacturing - industrial distributor with negotiated pricing

**Primary language:** SQL
**Tags:** `pricing`, `dbt`, `sql`, `causal-inference`, `elasticity`, `dimensional-modelling`

---

> **Implementation note.** The catalogue specifies **SQL** for this
> project and that remains the target. This repository ships a runnable
> **Python** reference implementation of the core differentiator so the
> behaviour is executable and tested today; port it to SQL as step one
> of your own build.

## The problem

Sales representatives have discount authority. Margin falls 2.3 points year on year and leadership blames market pressure. In reality it is a mixture of genuine price erosion, a shift toward lower-margin product lines, and one region discounting 40% more than anyone else - three completely different problems requiring three different responses, all invisible inside a single margin number.

## ⭐ The differentiator

A **price-volume-mix bridge decomposition** separates rate erosion from mix shift, combined with **elasticity estimated against the confounding**, not from a naive regression of volume on price. In observational sales data, discounts are *given to* customers who were going to buy less anyway - so a naive elasticity carries the sign of the confounder rather than the causal effect. A generic pricing analysis regresses units on price, reports an elasticity, and recommends a price cut that destroys margin.

This is the sentence to lead with when someone asks you to walk through the
project. Everything else in this repo exists to make it true and to prove it.

## Data

A documented synthetic generator with a **known true elasticity per segment** and a deliberately confounded discount-assignment mechanism, so the analysis can be scored against ground truth. Structure informed by publicly documented B2B distribution pricing patterns.

> No paid API key is required to run or demo this project. Where a paid
> service would add value it is wired as an optional enhancement behind an
> interface with an offline mock as the default implementation.

## Stack

- PostgreSQL / DuckDB - the SQL is the primary artefact
- dbt for the transformation layer, with tests
- Python (statsmodels) for the elasticity estimation only
- Streamlit for the policy simulator
- dbt tests + pytest

## Core capabilities

- Dimensional model of transactions, price-waterfall components, and customer/product hierarchies
- Price-volume-mix bridge with drill-down to segment, region and representative
- Segment-level elasticity with the confounding addressed and confidence intervals reported
- Policy simulator: propose a discount-authority matrix, see modelled margin and volume impact with uncertainty bands
- Representative-level discount outlier detection that controls for customer mix

## Repository layout

```
models/staging/
models/marts/
analysis/elasticity/
sim/
generator/
app/
tests/
```

## Build plan

1. Generator first, with a true elasticity you choose and a confounder you design. This is what makes the estimate scoreable.
2. Dimensional model and the bridge. Get the bridge to sum exactly before trusting any component.
3. Elasticity with the confounding handled - and show the naive estimate alongside it, because the contrast is the argument.
4. Policy simulator last.

## Testing strategy

Assert the recovered elasticity falls **within its stated confidence interval of the generator's true value** per segment. Assert the bridge components **sum exactly** to the total margin delta - a silent off-by-one in a bridge is the classic error that invalidates the whole analysis while looking completely reasonable.

Tests assert **correctness**, not merely that the code runs. A green suite on
this repo is a claim about behaviour under adversarial conditions; treat any
test that would pass against a deliberately broken implementation as a bug in
the test.

## Quality & safety layer

dbt tests enforce referential integrity and non-negative quantities on the fact table. Every elasticity estimate ships with its interval; the simulator refuses to display a point estimate without one.

## Measurable outcome

> The 2.3-point margin decline decomposes to 0.4 points price erosion, 1.6 points mix shift and 0.3 points discount policy - redirecting the response from a price increase to a product-mix intervention.

State it in these terms — business units, not technical ones — in your CV
bullet and in the first thirty seconds of describing the project.

## Interview questions this project answers

- **Why is a naive price-elasticity regression usually wrong sign?**
- **Walk me through a price-volume-mix bridge.**
- **Your bridge does not sum. What went wrong?**

## What this deliberately is *not*

- Not a price-optimisation engine. It diagnoses first, because optimising the wrong quantity is how margin is lost.
- Not a causal-inference paper - it uses the minimum rigour needed to avoid a backwards answer.


## Run it now

```bash
python -m unittest discover -s tests -v   # the suite
python -m src.demo                        # the 60-second artefact
```

Requires Python 3.11+. The runnable core uses **only the standard
library** (including `sqlite3`), so there is nothing to install.

## Getting started

```bash
git clone <your-fork-url> marginbridge
cd marginbridge
pip install -e .
python -m generator --months 24
dbt build
python -m analysis.elasticity --compare-naive
streamlit run app/main.py
pytest && dbt test
```

Docker is supported but optional — every path above works on a plain
Windows/macOS/Linux laptop without a cloud account.

## Definition of done

- [ ] The differentiator above is implemented, and a test proves it
- [ ] The measurable outcome is produced by a command anyone can run
- [ ] `README` explains the one decision a generic version gets wrong
- [ ] CI runs the full suite on every push and is green on `main`
- [ ] A recruiter can see the headline artefact in under 60 seconds

## Licence

MIT — see [LICENSE](LICENSE).
