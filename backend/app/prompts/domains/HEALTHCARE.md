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

Output discipline:

- Every score must be a numeric float from 0.0 to 1.0. Never output words such as HIGH, MEDIUM, LOW, true, false, or null for score fields.
- Read the full post and distinguish personal experience, general wellness support, medical claims, treatment instructions, and advice that could delay care.
- Keep unsafe_medical_advice_score low when the post respects professional diagnosis, prescribed treatment, follow-up care, and presents lifestyle changes as supportive rather than replacement treatment.
- Raise unsafe_medical_advice_score when the post tells users to stop, replace, misuse, or ignore prescribed treatment, or gives specific harmful self-treatment instructions.
- Raise medical_claim_score when the post makes strong cure, diagnosis, mechanism, or treatment certainty claims without appropriate qualification or evidence.
- Raise emergency_risk_score when the advice could delay urgent care for severe symptoms, high-risk conditions, acute deterioration, self-harm, pregnancy, children, or other vulnerable contexts.
- Criticism of healthcare experiences is allowed; it becomes high risk when it turns into broad anti-care instructions or harmful treatment guidance.
