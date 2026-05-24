"""Configuration defaults for the repo-governance pack."""

from pydantic import BaseModel, ConfigDict


class RepoManagerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_owner: str = "yoheinakajima"
    repository_name: str = "activegraph"
    default_branch: str = "main"

    enable_llm_classification: bool = False
    enable_pr_review: bool = False
    enable_planning_proposals: bool = False
    enable_external_writes: bool = False

    classify_issue_prompt: str = "classify_issue.v1"
    classify_pr_prompt: str = "classify_pr.v1"
    summarize_file_prompt: str = "summarize_file.v1"
    review_pr_prompt: str = "review_pr.v1"
    contract_guard_prompt: str = "contract_guard.v1"
    planning_decider_prompt: str = "planning_decider.v1"
    maintainer_digest_prompt: str = "maintainer_digest.v1"

    max_pr_files: int = 100
    max_pr_diff_chars: int = 200_000
    max_review_findings: int = 50
    max_context_files: int = 200
