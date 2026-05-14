# HEALTHCARE Prompt

Domain: health advice, treatment experience, medication, telemedicine, disease support communities.

Safe content examples:

- Personal recovery stories that respect medical diagnosis and professional treatment.
- Lifestyle support such as diet, sleep, exercise, stress reduction, or doctor follow-up.
- Encouraging users to seek diagnosis or emergency care when appropriate.

Main risks:

- `unsafe_medical_advice_score`: telling users to stop prescribed treatment, harmful self-treatment, dangerous dosing, miracle cures, anti-doctor conspiracy instructions.
- `emergency_risk_score`: symptoms or advice that could delay urgent care, severe pain, breathing problems, neurological signs, self-harm risk.
- `medical_claim_score`: strong cure claims, diagnosis claims, unverified treatment certainty.
- `scam_score`: paid miracle product or supplement scheme.
- `toxicity_score`: abusive or shaming language around illness.

High-confidence violation patterns:

- "throw away prescribed medicine", "doctors only want profit", "cure GERD/cancer/diabetes naturally", ingesting acidic substances on ulcers, replacing antibiotics with unsafe tricks.
- Posts that undermine professional care and give specific harmful instructions.

Calibration:

- Sharing experience after seeing a doctor is usually low risk.
- Complementary lifestyle advice is usually low risk when it does not replace treatment.
- Specific instructions to stop medication should strongly raise unsafe_medical_advice_score.
