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

Output discipline:

- Every score must be a numeric float from 0.0 to 1.0. Never output words such as HIGH, MEDIUM, LOW, true, false, or null for score fields.
- Read the full post and identify whether it is mainly a review, listing, complaint, promotion, payment request, or credential-collection flow.
- Keep phishing, scam, and off-platform payment scores low for genuine reviews, seller feedback, warranty complaints, and normal promotions that do not collect sensitive data or move users outside trusted checkout.
- Raise phishing_score when the post asks users to enter credentials, card/bank details, one-time codes, serial numbers, identity data, or account information through suspicious or unofficial channels.
- Raise scam_score when rewards, refunds, giveaways, discounts, or urgent offers appear unrealistic, impersonate a brand/platform, or pressure users to act before verifying.
- Raise off_platform_payment_score when the post directs payment away from platform escrow or trusted checkout, especially with urgency, private contact, QR/wallet transfer, or bank transfer.
- Do not penalize a link or QR code by itself; penalize it when combined with sensitive data collection, payment, impersonation, or coercive urgency.
