from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModerationDomain(str, Enum):
    EDTECH = "EDTECH"
    ECOMMERCE = "ECOMMERCE"
    REAL_ESTATE = "REAL_ESTATE"
    HEALTHCARE = "HEALTHCARE"
    ENTERPRISE_HR = "ENTERPRISE_HR"
    UNKNOWN = "UNKNOWN"


class PrimaryRisk(str, Enum):
    NONE = "NONE"
    SPAM = "SPAM"
    SCAM = "SCAM"
    TOXICITY = "TOXICITY"
    THREAT = "THREAT"
    HATE = "HATE"
    ACADEMIC_INTEGRITY = "ACADEMIC_INTEGRITY"
    CREDENTIAL_FRAUD = "CREDENTIAL_FRAUD"
    PHISHING = "PHISHING"
    COUNTERFEIT = "COUNTERFEIT"
    OFF_PLATFORM_PAYMENT = "OFF_PLATFORM_PAYMENT"
    FAKE_LISTING = "FAKE_LISTING"
    UNREALISTIC_RETURN = "UNREALISTIC_RETURN"
    DEPOSIT_RISK = "DEPOSIT_RISK"
    DISCRIMINATION = "DISCRIMINATION"
    UNSAFE_MEDICAL_ADVICE = "UNSAFE_MEDICAL_ADVICE"
    EMERGENCY_RISK = "EMERGENCY_RISK"
    CONFIDENTIAL_DATA = "CONFIDENTIAL_DATA"
    INSIDER_THREAT = "INSIDER_THREAT"


class ModerationDecision(str, Enum):
    ALLOW = "ALLOW"
    WARN_ALLOW = "WARN_ALLOW"
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ContentStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    PUBLISHED_WITH_WARNING = "PUBLISHED_WITH_WARNING"
    REJECTED = "REJECTED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"


ROUTABLE_DOMAIN_VALUES = {
    ModerationDomain.EDTECH.value,
    ModerationDomain.ECOMMERCE.value,
    ModerationDomain.REAL_ESTATE.value,
    ModerationDomain.HEALTHCARE.value,
    ModerationDomain.ENTERPRISE_HR.value,
}
SUPPORTED_DOMAIN_VALUES = ROUTABLE_DOMAIN_VALUES | {ModerationDomain.UNKNOWN.value}
PRIMARY_RISK_VALUES = {risk.value for risk in PrimaryRisk}

GENERIC_SCORE_KEYS = (
    "toxicity_score",
    "spam_score",
    "scam_score",
    "threat_score",
    "hate_score",
    "medical_claim_score",
    "financial_risk_score",
)
DOMAIN_SCORE_KEYS = {
    ModerationDomain.EDTECH.value: ("academic_integrity_score", "credential_fraud_score"),
    ModerationDomain.ECOMMERCE.value: (
        "phishing_score",
        "counterfeit_score",
        "off_platform_payment_score",
    ),
    ModerationDomain.REAL_ESTATE.value: (
        "fake_listing_score",
        "unrealistic_return_score",
        "deposit_risk_score",
        "discrimination_score",
    ),
    ModerationDomain.HEALTHCARE.value: (
        "unsafe_medical_advice_score",
        "emergency_risk_score",
    ),
    ModerationDomain.ENTERPRISE_HR.value: (
        "confidential_data_score",
        "insider_threat_score",
    ),
}
DOMAIN_SCORE_FIELD_BY_DOMAIN = {
    ModerationDomain.EDTECH.value: "edtech_scores",
    ModerationDomain.ECOMMERCE.value: "ecommerce_scores",
    ModerationDomain.REAL_ESTATE.value: "real_estate_scores",
    ModerationDomain.HEALTHCARE.value: "healthcare_scores",
    ModerationDomain.ENTERPRISE_HR.value: "enterprise_hr_scores",
}


class ModerationRequest(BaseModel):
    text: str = Field(min_length=1)
    image_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DomainClassificationResult(BaseModel):
    detected_domain: ModerationDomain
    domain_confidence: float = Field(ge=0.0, le=1.0)
    analysis_profile: str
    content_prompt_profile: str
    image_prompt_profile: str = ""
    requires_domain_review: bool = False


class ContentSignals(BaseModel):
    language: str = "unknown"
    topic_labels: list[str] = Field(default_factory=list)
    primary_risk: PrimaryRisk = PrimaryRisk.NONE
    matched_signals: list[str] = Field(default_factory=list)
    domain_score_keys: list[str] = Field(default_factory=list)
    agent_version: str = "llm-content-v1"
    generic_scores: dict[str, float] = Field(default_factory=dict)
    edtech_scores: dict[str, float] | None = None
    ecommerce_scores: dict[str, float] | None = None
    real_estate_scores: dict[str, float] | None = None
    healthcare_scores: dict[str, float] | None = None
    enterprise_hr_scores: dict[str, float] | None = None


class ImageSignals(BaseModel):
    has_image: bool = True
    image_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    image_policy_labels: list[str] = Field(default_factory=list)
    image_ocr_text: str = ""
    image_matched_signals: list[str] = Field(default_factory=list)
    agent_version: str = "llm-image-v1"


class ModerationResponse(BaseModel):
    content_id: str
    status: ContentStatus
    decision: ModerationDecision
    message: str
    detected_domain: ModerationDomain
    analysis_profile: str
    workflow: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    explanations: dict[str, Any] = Field(default_factory=dict)


class ReviewerDecision(str, Enum):
    APPROVE_PUBLISH = "APPROVE_PUBLISH"
    REJECT_CONTENT = "REJECT_CONTENT"


class ReviewerDecisionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)
    decision: ReviewerDecision
    note: str = ""


class ModerationRecord(BaseModel):
    content_id: str
    request: ModerationRequest
    response: ModerationResponse
    review_note: str = ""
    reviewer_id: str = ""
