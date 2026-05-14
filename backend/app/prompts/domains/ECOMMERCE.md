# ECOMMERCE Prompt

Domain: marketplace listings, product reviews, promotions, sellers, refunds, brand campaigns.

Safe content examples:

- Honest product reviews with pros and cons.
- Complaints about warranty, shipping, service quality, or product defects.
- Normal marketplace promotions that stay on-platform and do not request sensitive data.

Main risks:

- `phishing_score`: fake reward links, credential or card collection, serial-number traps, suspicious campaign domains, urgency-driven claim forms.
- `counterfeit_score`: fake branded products, replica goods, counterfeit labels, suspicious brand claims.
- `off_platform_payment_score`: QR payment, bank transfer, direct wallet transfer, platform escrow bypass, "inbox to pay".
- `scam_score`: unrealistic refund/reward schemes, impersonated brand campaigns, money-back bait.
- `spam_score`: repetitive low-value promotional copy.

High-confidence violation patterns:

- "scan QR to receive money", "enter card information", "serial number verification", fake event domains, "only until midnight".
- Product review text that pivots into a reward, refund, or external payment flow.

Calibration:

- Negative reviews are allowed when they do not request credentials or payment.
- A QR code or link is not automatically high risk; raise score when paired with payment, card, credential, serial number, or urgent reward language.
