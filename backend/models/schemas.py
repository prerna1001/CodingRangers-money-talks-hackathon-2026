"""Canonical data contracts shared across the whole backend.

This is the ONE shared file between Claude's agentic pipeline and Codex's
deterministic analytics core (see BACKEND_TASK_SPLIT.md section 4). Claude
owns edits to this file. Codex imports these types rather than redefining
them; if a new field is needed, leave a `# SCHEMA REQUEST:` comment at the
call site instead of editing here directly.

Every shape below corresponds 1:1 to a JSON example in HACKATHON_PLAN.md
section 4 ("Data Contracts") and the agent I/O shapes in section 6-10.
Field names and nesting intentionally match those examples exactly.
"""

from __future__ import annotations

import operator
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class AccountType(str, Enum):
    REVENUE = "revenue"
    COGS = "cogs"
    OPEX = "opex"
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"


class CounterpartyType(str, Enum):
    CUSTOMER = "customer"
    VENDOR = "vendor"
    EMPLOYEE = "employee"
    OTHER = "other"


class ClaimType(str, Enum):
    """Load-bearing distinction -- see plan section 4.5."""

    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class Recurrence(str, Enum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"
    SEASONAL = "seasonal"
    UNCLASSIFIED = "unclassified"


class RunSafety(str, Enum):
    """Data QA gate outcome -- plan section 6.2."""

    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    BLOCKED = "blocked"


class WarningSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemoryType(str, Enum):
    BUSINESS_PATTERN = "business_pattern"
    ENTITY_FACT = "entity_fact"
    ENTITY_ALIAS = "entity_alias"
    ANOMALY_HISTORY = "anomaly_history"
    USER_CORRECTION = "user_correction"
    STYLE_PREFERENCE = "style_preference"


class MemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    RETIRED = "retired"


class MemorySource(str, Enum):
    SYSTEM = "system"
    USER = "user"


class GuardrailStatus(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_CAVEATS = "approved_with_caveats"
    NEEDS_REVISION = "needs_revision"
    BLOCKED_DUE_TO_DATA_QUALITY = "blocked_due_to_data_quality"


class AgentStatus(str, Enum):
    WAITING = "waiting"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    REVISED = "revised"


class StressStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_RUN = "not_run"


# ---------------------------------------------------------------------------
# 4.1 Canonical transaction row
# ---------------------------------------------------------------------------


class CanonicalTransaction(BaseModel):
    txn_id: str
    source_file_id: str
    source_row: int
    posted_date: date
    period_id: str
    account_id: str
    account_name: str
    account_type: AccountType
    category: str
    counterparty_id: str | None = None
    counterparty_name: str | None = None
    counterparty_type: CounterpartyType | None = None
    amount: float
    currency: str = "USD"
    memo: str = ""
    is_recurring: bool = False
    recurrence_key: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    flags: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 4.2 Canonical period summary
# ---------------------------------------------------------------------------


class PeriodLine(BaseModel):
    account_id: str
    account_name: str
    account_type: AccountType
    amount: float


class PeriodDerived(BaseModel):
    total_revenue: float | None = None
    gross_profit: float | None = None
    operating_expenses: float | None = None
    net_income: float | None = None
    ending_cash: float | None = None


class PeriodSummary(BaseModel):
    period_id: str
    start_date: date
    end_date: date
    currency: str = "USD"
    lines: list[PeriodLine] = Field(default_factory=list)
    derived: PeriodDerived = Field(default_factory=PeriodDerived)


# ---------------------------------------------------------------------------
# 4.3 Company profile (Profile Builder output)
# ---------------------------------------------------------------------------


class PeriodInfo(BaseModel):
    period_id: str
    start_date: date
    end_date: date


class AvailableFile(BaseModel):
    file_id: str
    type: Literal["transaction_csv", "period_summary_csv"]
    period_id: str
    sha256: str | None = None
    row_count: int | None = None


class CompanyProfileCore(BaseModel):
    company_id: str
    company_name: str
    industry: str
    business_model: str
    fiscal_year_start_month: int = 1
    reporting_basis: Literal["accrual", "cash"] = "accrual"
    base_currency: str = "USD"
    primary_revenue_streams: list[str] = Field(default_factory=list)
    known_seasonality: list[str] = Field(default_factory=list)
    materiality_threshold_usd: float = 5000.0
    materiality_threshold_pct: float = 0.05


class CompanyProfile(BaseModel):
    company_profile: CompanyProfileCore
    periods: list[PeriodInfo] = Field(default_factory=list)
    available_files: list[AvailableFile] = Field(default_factory=list)
    entity_aliases: dict[str, list[str]] = Field(default_factory=dict)
    normalization_report: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 4.4 Fact table -- the only thing the Analyst may cite
# ---------------------------------------------------------------------------


class BasisPoint(BaseModel):
    period: str
    value: float


class Basis(BaseModel):
    current: BasisPoint
    prior: BasisPoint


class Significance(BaseModel):
    trailing_mean: float | None = None
    trailing_sd: float | None = None
    z: float | None = None
    outside_control_limits: bool = False
    insufficient_history: bool = False


class Fact(BaseModel):
    fact_id: str
    kind: Literal[
        "variance",
        "driver",
        "bridge_component",
        "concentration",
        "recurrence",
        "reconciliation",
        "run_rate",
        "anomaly",
    ]
    label: str
    value: float
    unit: str = "USD"
    formatted: str
    pct: float | None = None
    basis: Basis | None = None
    significance: Significance | None = None
    evidence_txn_ids: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# 4.5 Explanation contract
# ---------------------------------------------------------------------------


class Claim(BaseModel):
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    claim_type: ClaimType

    @model_validator(mode="after")
    def fact_claims_need_evidence(self) -> "Claim":
        if self.claim_type == ClaimType.FACT and not self.fact_ids:
            raise ValueError("claim_type == 'fact' requires at least one fact_id")
        return self


class DriverEvidence(BaseModel):
    counterparty_name: str
    amount: float
    txn_ids: list[str] = Field(default_factory=list)


class Driver(BaseModel):
    driver: str
    amount: float
    share_of_gross_change_pct: float
    share_of_net_change_pct: float | None = None
    recurrence: Recurrence = Recurrence.UNCLASSIFIED
    evidence: list[DriverEvidence] = Field(default_factory=list)
    confidence: float = 1.0


class MemoryInfluence(BaseModel):
    memory_id: str
    effect: str


class Explanation(BaseModel):
    headline: str
    summary: str
    claims: list[Claim] = Field(default_factory=list)
    drivers: list[Driver] = Field(default_factory=list)
    risks_or_caveats: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    memory_influence: list[MemoryInfluence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 6.2 Data QA report
# ---------------------------------------------------------------------------


class ReconciliationLine(BaseModel):
    account_id: str
    summary: float
    transactions: float
    difference: float
    difference_pct: float
    status: Literal["pass", "warn", "fail"]


class ReconciliationReport(BaseModel):
    by_account: list[ReconciliationLine] = Field(default_factory=list)
    worst_difference_pct: float = 0.0


class QAWarning(BaseModel):
    code: str
    message: str
    severity: WarningSeverity


class QAReport(BaseModel):
    status: RunSafety
    data_quality_score: float
    reconciliation: ReconciliationReport
    warnings: list[QAWarning] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    safe_to_analyze: bool


# ---------------------------------------------------------------------------
# 8. Memory
# ---------------------------------------------------------------------------


class MemoryScope(BaseModel):
    accounts: list[str] = Field(default_factory=list)
    counterparties: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class Memory(BaseModel):
    memory_id: str
    company_id: str
    memory_type: MemoryType
    content: str
    scope: MemoryScope = Field(default_factory=MemoryScope)
    evidence_run_ids: list[str] = Field(default_factory=list)
    corroboration_count: int = 0
    contradiction_count: int = 0
    confidence: float = 0.5
    status: MemoryStatus = MemoryStatus.CANDIDATE
    created_at: datetime
    last_reinforced_at: datetime
    source: MemorySource = MemorySource.SYSTEM
    user_edited: bool = False


# ---------------------------------------------------------------------------
# 9. RAG
# ---------------------------------------------------------------------------


class RetrievedChunk(BaseModel):
    chunk_id: str
    source: str
    text: str
    relevance_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    used_by_claim: str | None = None


# ---------------------------------------------------------------------------
# 10.1 Numeric grounding verifier
# ---------------------------------------------------------------------------


class GroundingViolationType(str, Enum):
    UNGROUNDED_NUMBER = "ungrounded_number"
    UNCITED_CLAIM = "uncited_claim"
    HALLUCINATED_ENTITY = "hallucinated_entity"
    DIRECTION_ERROR = "direction_error"


class GroundingViolation(BaseModel):
    type: GroundingViolationType
    severity: Literal["critical", "warning"]
    detail: str
    claim_index: int | None = None


class EntityCheck(BaseModel):
    checked: int = 0
    hallucinated: int = 0


class DirectionCheck(BaseModel):
    checked: int = 0
    errors: int = 0


class GroundingReport(BaseModel):
    grounded_numbers: int
    total_numbers: int
    grounding_rate: float
    violations: list[GroundingViolation] = Field(default_factory=list)
    entity_check: EntityCheck = Field(default_factory=EntityCheck)
    direction_check: DirectionCheck = Field(default_factory=DirectionCheck)

    @property
    def has_critical_violation(self) -> bool:
        return any(v.severity == "critical" for v in self.violations)


# ---------------------------------------------------------------------------
# 6.6 Guardrail result
# ---------------------------------------------------------------------------


class GuardrailResult(BaseModel):
    status: GuardrailStatus
    grounding: GroundingReport
    notes: list[str] = Field(default_factory=list)
    revision_feedback: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 12. Stress test
# ---------------------------------------------------------------------------


class StressResult(BaseModel):
    scenario_id: str
    name: str
    status: StressStatus
    detail: str
    metrics: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 7.2 / 7.3 Orchestration
# ---------------------------------------------------------------------------


class AgentError(BaseModel):
    agent: str
    message: str
    recoverable: bool = True


class AgentTimelineEntry(BaseModel):
    agent: str
    status: AgentStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    safety_notes: list[str] = Field(default_factory=list)


def _merge_dicts_sum(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Reducer for token_usage: sums matching numeric keys instead of
    overwriting, so a node's return value only needs to carry its OWN
    incremental usage -- correct whether nodes ran sequentially or in
    parallel (plan section 7.1's Memory/RAG/Analytics fan-out).
    """
    merged = dict(a)
    for key, value in b.items():
        merged[key] = merged.get(key, 0) + value
    return merged


def _merge_dicts_overwrite(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    merged = dict(a)
    merged.update(b)
    return merged


class RunState(TypedDict, total=False):
    """LangGraph state object -- see plan section 7.2.

    Kept as a TypedDict (not a BaseModel) because LangGraph's StateGraph
    reads/writes it as a plain mapping; the values inside are still the
    Pydantic models defined above.

    `timeline`, `timings`, `token_usage`, and `errors` use additive
    reducers (Annotated[..., reducer_fn]) because Memory, RAG, and the
    Analytics Engine run in the same parallel superstep (plan section
    7.1) -- each returns only ITS OWN delta, and LangGraph merges the
    deltas instead of the default last-write-wins overwrite, which would
    silently drop two of the three branches' contributions.
    """

    run_id: str
    company_id: str
    current_period: str
    prior_period: str

    # Inputs (set once, before the graph runs)
    company_profile_core: CompanyProfileCore
    available_files: list[AvailableFile]
    known_aliases: dict[str, list[str]]

    transactions: list[CanonicalTransaction]
    period_summaries: list[PeriodSummary]

    profile: CompanyProfile
    qa_report: QAReport
    facts: list[Fact]
    memories: list[Memory]
    retrieved: list[RetrievedChunk]
    explanation: Explanation | None
    grounding_report: GroundingReport | None
    guardrail_result: GuardrailResult | None
    stress_results: list[StressResult]

    # Final rendered outputs (plan section 6.8 / 15.2)
    report_markdown: str
    dashboard_payload: dict[str, Any]
    board_update: str

    revision_count: int
    errors: Annotated[list[AgentError], operator.add]
    timeline: Annotated[list[AgentTimelineEntry], operator.add]
    timings: Annotated[dict[str, float], _merge_dicts_overwrite]
    token_usage: Annotated[dict[str, int], _merge_dicts_sum]
