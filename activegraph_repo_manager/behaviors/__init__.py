"""Behavior module registry placeholders."""

behaviors = (
    "activegraph_repo_manager.behaviors.ingest_github",
    "activegraph_repo_manager.behaviors.index_repo",
    "activegraph_repo_manager.behaviors.load_planning_docs",
    "activegraph_repo_manager.behaviors.classify_issue",
    "activegraph_repo_manager.behaviors.classify_pr",
    "activegraph_repo_manager.behaviors.link_issue_to_planning",
    "activegraph_repo_manager.behaviors.analyze_pr_diff",
    "activegraph_repo_manager.behaviors.contract_guard",
    "activegraph_repo_manager.behaviors.review_pr",
    "activegraph_repo_manager.behaviors.propose_planning_patch",
    "activegraph_repo_manager.behaviors.apply_approved_actions",
    "activegraph_repo_manager.behaviors.digest",
)
