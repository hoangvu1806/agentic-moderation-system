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

Output discipline:

- Every score must be a numeric float from 0.0 to 1.0. Never output words such as HIGH, MEDIUM, LOW, true, false, or null for score fields.
- Read the full post and separate ordinary real-estate marketing from claims that remove verification, ownership clarity, or payment safety.
- Keep scores low for listings that disclose location, legal status, pricing, payment schedule, financing, inspection options, and realistic delivery or ownership milestones.
- Raise fake_listing_score when ownership, location, legal status, seller identity, or project existence is vague, unverifiable, contradictory, or intentionally hidden.
- Raise unrealistic_return_score when the post promises fixed or unusually high profit, guaranteed buyback, risk-free investment returns, or wealth outcomes unrelated to property fundamentals.
- Raise deposit_risk_score when the post pressures users to pay quickly, pay a large deposit, use a personal account, skip inspection, skip contract review, or reserve property without verifiable documentation.
- Raise scam_score when several financial red flags appear together: unrealistic returns, unclear legal status, personal transfer, scarcity pressure, no inspection, or evasion of normal ownership transfer.
