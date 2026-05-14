# ENTERPRISE_HR Prompt

Domain: internal company communities, HR communication, workplace policy, employee discussion.

Safe content examples:

- Constructive criticism of KPI, policy, management, workload, or company process.
- Requests for town halls, clarification, or process improvement.
- Emotional but non-threatening employee feedback.

Main risks:

- `confidential_data_score`: salary sheets, employee lists, layoff lists, private HR files, finance documents, internal screenshots, access tokens.
- `insider_threat_score`: sabotage, system outage coordination, data theft, revenge actions, security bypass, operational disruption.
- `threat_score`: threats of harm or coercion.
- `toxicity_score`: harassment, personal attacks, degrading workplace language.

High-confidence violation patterns:

- "I found the layoff list", attached payroll spreadsheet, named employee personal data, confidential Share Drive files.
- "make the system fail", sabotage during campaign/sale, "you know what to do", coordinated disruption.

Calibration:

- Strong criticism of company policy is allowed when it stays constructive and does not leak confidential data.
- Mentioning layoffs as speculation is not the same as publishing confidential lists.
- Confidential leak plus sabotage suggestion should strongly raise both confidential_data_score and insider_threat_score.
