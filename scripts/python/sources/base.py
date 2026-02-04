"""Base source abstraction for work items."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class WorkItem:
    key: str
    title: str
    description: str = ""
    status: str = ""
    acceptance_criteria: str = ""
    assignee: str | None = None
    labels: list[str] = field(default_factory=list)
    parent_key: str | None = None
    item_type: str = "task"
    source: str = "jira"
    source_url: str | None = None
    children: list[str] = field(default_factory=list)


class WorkItemSource(Protocol):
    """Protocol for source adapters (JIRA, GitHub Projects, MCP, etc.)."""

    source_name: str

    def validate_key(self, key: str) -> bool:
        raise NotImplementedError

    def fetch_item(self, key: str) -> WorkItem:
        raise NotImplementedError

    def fetch_children(self, key: str) -> list[WorkItem]:
        raise NotImplementedError


