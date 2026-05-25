"""Phase 0 strict schemas for the ActiveGraph repo-governance pack."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkType(str, Enum):
    bugfix = "bugfix"
    feature = "feature"
    docs = "docs"
    refactor = "refactor"
    infra = "infra"
    observability = "observability"
    store_backend = "store_backend"


class Scope(str, Enum):
    S = "S"
    M = "M"
    L = "L"
    repository = "repository"
    module = "module"
    file = "file"
    line = "line"


class Risk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PlanningPriority(str, Enum):
    should_have = "should_have"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TriageUrgency(str, Enum):
    low = "low"
    normal = "normal"
    urgent = "urgent"


class LifecycleStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    closed = "closed"


class ReviewSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class ReviewCategory(str, Enum):
    correctness = "correctness"
    security = "security"
    performance = "performance"
    maintainability = "maintainability"
    contract = "contract"


class ProposalStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    applied = "applied"


class EvidenceRef(StrictModel):
    source: str
    locator: str
    note: str | None = None


class ExternalObject(StrictModel):
    external_key: str
    source: str
    external_metadata: dict[str, Any] = Field(default_factory=dict)


class Repository(ExternalObject):
    owner: str
    name: str
    default_branch: str


class RepoFile(StrictModel):
    path: str
    language: str | None = None
    size_bytes: int | None = None


class Symbol(StrictModel):
    name: str
    kind: str
    file_path: str
    line_start: int | None = None
    line_end: int | None = None


class TestSurface(StrictModel):
    name: str
    location: str
    kind: str


class RepoSnapshot(ExternalObject):
    repository_external_key: str
    commit_sha: str
    files: list[RepoFile] = Field(default_factory=list)
    symbols: list[Symbol] = Field(default_factory=list)
    tests: list[TestSurface] = Field(default_factory=list)


class PlanningItem(StrictModel):
    external_key: str
    title: str
    priority: PlanningPriority = PlanningPriority.medium
    status: LifecycleStatus = LifecycleStatus.open
    work_type: WorkType | None = None


class Issue(ExternalObject):
    number: int
    title: str
    status: LifecycleStatus
    urgency: TriageUrgency = TriageUrgency.normal


class PullRequest(ExternalObject):
    number: int
    title: str
    status: LifecycleStatus
    base_branch: str
    head_branch: str
    work_type: WorkType | None = None


class PRDiff(ExternalObject):
    pull_request_external_key: str
    files_changed: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    external_metadata: dict[str, Any] = Field(default_factory=dict)


class CheckRun(ExternalObject):
    name: str
    status: LifecycleStatus
    conclusion: str | None = None


class ReviewFinding(StrictModel):
    finding_id: str
    severity: ReviewSeverity
    category: ReviewCategory
    blocking: bool = False
    summary: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    suggested_fix: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_external_action: bool = False


class Decision(StrictModel):
    decision: str
    rationale: str
    risk: Risk = Risk.low
    evidence: list[EvidenceRef] = Field(default_factory=list)


class PlanningPatchProposal(StrictModel):
    proposal_id: str
    status: ProposalStatus = ProposalStatus.proposed
    planning_item_external_key: str
    patch: dict[str, Any] = Field(default_factory=dict)


class ExternalActionProposal(StrictModel):
    proposal_id: str
    status: ProposalStatus = ProposalStatus.proposed
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MaintainerDigest(StrictModel):
    digest_id: str
    repository_external_key: str
    summary: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
