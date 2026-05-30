"""Pack assembly for activegraph_repo_manager."""

from dataclasses import dataclass

from .behaviors import behaviors as behavior_modules
from .relations import RELATIONS
from .tools import tools as tool_modules


SCHEMA_TYPES = (
    "activegraph_repo_manager.schemas.Repository",
    "activegraph_repo_manager.schemas.RepoFile",
    "activegraph_repo_manager.schemas.Symbol",
    "activegraph_repo_manager.schemas.TestSurface",
    "activegraph_repo_manager.schemas.RepoSnapshot",
    "activegraph_repo_manager.schemas.PlanningItem",
    "activegraph_repo_manager.schemas.Issue",
    "activegraph_repo_manager.schemas.PullRequest",
    "activegraph_repo_manager.schemas.PRDiff",
    "activegraph_repo_manager.schemas.CheckRun",
    "activegraph_repo_manager.schemas.ReviewFinding",
    "activegraph_repo_manager.schemas.Decision",
    "activegraph_repo_manager.schemas.PlanningPatchProposal",
    "activegraph_repo_manager.schemas.ExternalActionProposal",
    "activegraph_repo_manager.schemas.MaintainerDigest",
)

PROMPT_FILES = (
    "classify_issue.v1.md",
    "classify_pr.v1.md",
    "summarize_file.v1.md",
    "review_pr.v1.md",
    "contract_guard.v1.md",
    "planning_decider.v1.md",
    "maintainer_digest.v1.md",
)

FIXTURE_FILES = (
    "issue_23_open_telemetry.json",
    "pr_24_falkordb_eventstore.json",
    "repo_snapshot_minimal.json",
    "pr_diff_contract_sensitive.json",
    "llm_issue_classification.v1.json",
    "llm_pr_classification.v1.json",
    "llm_pr_review.v1.json",
    "llm_planning_decider.v1.json",
)

POLICIES = (
    "activegraph_repo_manager.policies.PLANNING_PATCH_APPROVAL_POLICY",
    "activegraph_repo_manager.policies.EXTERNAL_ACTION_APPROVAL_POLICY",
)


@dataclass(frozen=True)
class RepoManagerPack:
    name: str
    relations: tuple[str, ...]
    behavior_modules: tuple[str, ...]
    tool_modules: tuple[str, ...]
    schema_types: tuple[str, ...]
    settings_schema: str
    prompt_files: tuple[str, ...]
    fixture_files: tuple[str, ...]
    policies: tuple[str, ...]


pack = RepoManagerPack(
    name="activegraph_repo_manager",
    relations=RELATIONS,
    behavior_modules=behavior_modules,
    tool_modules=tool_modules,
    schema_types=SCHEMA_TYPES,
    settings_schema="activegraph_repo_manager.settings.RepoManagerSettings",
    prompt_files=PROMPT_FILES,
    fixture_files=FIXTURE_FILES,
    policies=POLICIES,
)
