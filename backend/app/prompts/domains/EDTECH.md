# EDTECH Prompt

Domain: online education, test preparation, tutoring, e-learning, certificates, admissions support.

Safe content examples:

- Personal study journeys based on effort, practice, teacher feedback, or learning strategy.
- Honest course reviews, including strong criticism or praise.
- Legitimate tutoring ads that do not promise cheating or fake credentials.

Main risks:

- `academic_integrity_score`: leaked exam questions, answer selling, exam proxy, test-room assistance, cheating services, private access to official exam boards.
- `credential_fraud_score`: fake certificates, guaranteed score or degree without effort, forged records, "clean profile" document fraud.
- `spam_score`: repetitive course promotion or aggressive enrollment bait.
- `toxicity_score`: harassment or degrading language in student/teacher discussions.

High-confidence violation patterns:

- "leaked questions", "exam board connection", "guaranteed 7.5", "VIP exam room", "proxy test", "fake certificate", "clean hồ sơ", "bao đậu".
- Posts that begin as a normal learning story but later offer cheating, leaked topics, or credential packages.

Calibration:

- Legitimate "score improvement in 3 months through practice" should keep academic_integrity_score and credential_fraud_score low.
- "Guaranteed score without studying" should strongly raise credential_fraud_score.
- "Exam questions from insiders" should strongly raise academic_integrity_score.

Output discipline:

- Every score must be a numeric float from 0.0 to 1.0. Never output words such as HIGH, MEDIUM, LOW, true, false, or null for score fields.
- Read the full post and identify the author's intent before scoring. A post may mix legitimate study advice, course promotion, and a later offer of misconduct.
- Keep integrity and fraud scores low when improvement is explained through effort, practice, feedback, study materials, lawful tutoring, or honest course reviews.
- Raise academic_integrity_score when the post offers unfair access to exam content, answers, impersonation, test-room assistance, bypassing exam rules, or coordination with insiders.
- Raise credential_fraud_score when the post promises credentials, scores, admissions outcomes, transcripts, or profiles without legitimate work, assessment, or verification.
- Treat guarantees as risky only when they imply bypassing learning or official assessment; ordinary marketing confidence is not enough by itself.
