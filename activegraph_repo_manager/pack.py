"""Pack assembly for activegraph_repo_manager."""

from dataclasses import dataclass

from .behaviors import behaviors as behavior_modules
from .tools import tools as tool_modules
from .relations import RELATIONS


@dataclass(frozen=True)
class RepoManagerPack:
    name: str
    relations: tuple[str, ...]
    behavior_modules: tuple[str, ...]
    tool_modules: tuple[str, ...]


pack = RepoManagerPack(
    name="activegraph_repo_manager",
    relations=RELATIONS,
    behavior_modules=behavior_modules,
    tool_modules=tool_modules,
)
