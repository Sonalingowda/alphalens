# AlphaLens Opportunity Plan Policy V1

## Status

APPROVED FOR MVP IMPLEMENTATION

## Purpose

Define a deterministic informational Opportunity Plan for valid BUY and SELL
opportunities.

This plan is decision-support context only. It is never an executable order,
fill instruction, position-sizing instruction, or guarantee of outcome.

## Policy Identity

- Policy ID: alphalens_opportunity_plan_v1
- Policy version: 1.0.0

## Eligible Decisions

- BUY: plan permitted
- SELL: plan permitted
- WAIT: plan absent

## Reference Price

The reference price is the point-in-time market close available by the
decision evidence cutoff.

## Entry

The informational entry region is an exact-price region:

entry_lower = reference_price
entry_upper = reference_price

Therefore the representative entry is the reference price itself.

## Price-Risk Construction

Price-risk distance is:

risk_distance = reference_price * 0.0003

This represents 0.03% of the reference price.

## Invalidation / Stop Loss

BUY:

stop_loss = entry - risk_distance

SELL:

stop_loss = entry + risk_distance

## Take Profit

V1 uses one informational take-profit level.

The target distance is:

target_distance = risk_distance * 1.5

BUY:

take_profit = entry + target_distance

SELL:

take_profit = entry - target_distance

## Risk / Reward

Risk:

R = directional distance from entry to stop loss.

Reward:

G = directional distance from entry to take profit.

Risk/reward:

RR = G / R

Therefore V1 produces:

RR = 1.50

## Account Risk Display

The account-risk percentage is NOT derived from the market signal.

The UI may display a configurable informational risk setting.

Default UI setting:

0.25%

This value is not persisted as a market-derived plan quantity and does not
constitute position sizing.

## Precision

All plan calculations use Decimal arithmetic.

Plan values are quantized using the existing project Decimal/rounding
conventions.

## Validity

The plan is valid only while its underlying opportunity and evidence remain
valid under the active decision lifecycle.

No independent execution expiry is implied by this policy.

## Missing Inputs

If reference price, direction, or any required calculation input is missing or
invalid, the complete plan is absent.

No partial plan is permitted.

## Directional Invariants

BUY:

stop_loss < entry_lower <= entry_upper < take_profit

SELL:

take_profit < entry_lower <= entry_upper < stop_loss

## Evidence

Every plan value must be reproducible from evidence available no later than the
decision evidence cutoff.

## Semantics

Risk/reward is geometric potential risk/reward.

It does not represent:

- probability of success
- expected return
- expectancy
- guaranteed profit
- executable fill price
- slippage-adjusted outcome
- transaction-cost-adjusted outcome
- position sizing

## Future Evolution

Changes to price-risk construction, target construction, target count, or
reference-price semantics require a new policy version.
