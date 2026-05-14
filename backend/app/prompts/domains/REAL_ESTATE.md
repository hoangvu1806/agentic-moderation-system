# REAL_ESTATE Prompt

Domain: property listings, land sales, rental posts, brokers, booking deposits, investment offers.

Safe content examples:

- Listings with location, legal status, pricing, payment schedule, and bank financing.
- Marketing language that is enthusiastic but still transparent.
- Posts that clearly disclose incomplete legal status or future delivery milestones.

Main risks:

- `fake_listing_score`: ghost projects, unverifiable ownership, no-site-visit pressure, vague legal status, misleading renders.
- `unrealistic_return_score`: guaranteed yearly returns, buyback promises, "profit guaranteed", Ponzi-like property investment.
- `deposit_risk_score`: urgent large deposit, personal bank account, pressure to book immediately, no inspection needed.
- `discrimination_score`: protected-class housing exclusion or discriminatory rental/sale conditions.
- `scam_score`: fake project, financial bait, personal transfer, coercive urgency.

High-confidence violation patterns:

- "45% per year guaranteed", "company buyback guarantee", "transfer deposit to director personal account", "no need to visit", "only for 10 fastest people".
- Legal evasion via investment authorization contracts instead of transparent property ownership.

Calibration:

- Standard booking and staged payment are not automatically risky if bank/payment/legal details are transparent.
- FOMO language alone is medium risk; FOMO plus personal deposit or guaranteed return is high risk.
