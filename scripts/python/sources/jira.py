"""JIRA source adapter using Atlassian Cloud API."""

from __future__ import annotations

import re
from typing import Any

from atlassian import Jira
from rich.console import Console

from .base import WorkItem

console = Console()


class JiraSource:
    source_name = "JIRA"

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        if not all([base_url, email, api_token]):
            raise ValueError(
                "Missing JIRA credentials. Set ATLASSIAN_BASE_URL, "
                "ATLASSIAN_EMAIL, and ATLASSIAN_API_TOKEN."
            )
        self.base_url = base_url
        self.client = Jira(url=base_url, username=email, password=api_token)

    def validate_key(self, key: str) -> bool:
        return bool(re.match(r"^[A-Z][A-Z0-9]+-\d+$", key))

    def fetch_item(self, key: str) -> WorkItem:
        issue = self.client.issue(key)
        fields = issue.get("fields", {})

        description = fields.get("description") or ""
        if isinstance(description, dict):
            description = self._extract_text_from_adf(description)

        acceptance_criteria = self._extract_acceptance_criteria(description)

        parent = fields.get("parent", {})
        parent_key = parent.get("key") if parent else None

        item_type = self._detect_item_type(fields)
        source_url = f"{self.base_url}/browse/{key}"

        return WorkItem(
            key=key,
            title=fields.get("summary", ""),
            description=description,
            status=fields.get("status", {}).get("name", ""),
            acceptance_criteria=acceptance_criteria,
            assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            labels=fields.get("labels", []),
            parent_key=parent_key,
            item_type=item_type,
            source="jira",
            source_url=source_url,
        )

    def fetch_children(self, key: str) -> list[WorkItem]:
        children: list[WorkItem] = []

        # First try: subtasks
        try:
            issue = self.client.issue(key)
            subtasks = issue.get("fields", {}).get("subtasks", [])
            if subtasks:
                for subtask in subtasks:
                    task_key = subtask.get("key")
                    if task_key:
                        children.append(self.fetch_item(task_key))
                return children
        except Exception as exc:  # pragma: no cover - non-deterministic API error
            console.print(f"[dim]Could not get subtasks: {exc}[/dim]")

        # Second try: JQL
        jql_queries = [
            f'parent = "{key}"',
            f'"Parent Link" = "{key}"',
            f'"Epic Link" = "{key}"',
        ]
        for jql in jql_queries:
            issues = self._search_jql(jql)
            if issues:
                for issue_data in issues:
                    task_key = issue_data.get("key")
                    if task_key:
                        children.append(self.fetch_item(task_key))
                return children

        return children

    def _search_jql(self, jql: str, max_results: int = 100) -> list[dict[str, Any]]:
        import urllib.parse

        encoded_jql = urllib.parse.quote(jql)
        url = f"rest/api/3/search/jql?jql={encoded_jql}&maxResults={max_results}&fields=key"
        try:
            response = self.client.get(url)
            return response.get("issues", [])
        except Exception as exc:  # pragma: no cover - non-deterministic API error
            console.print(f"[dim]JQL API error: {exc}[/dim]")
            return []

    def _detect_item_type(self, fields: dict[str, Any]) -> str:
        issue_type = fields.get("issuetype", {}).get("name", "").lower()
        if "epic" in issue_type:
            return "epic"
        if "feature" in issue_type:
            return "feature"
        if "story" in issue_type or "task" in issue_type or "bug" in issue_type:
            return "task"
        return "task"

    def _extract_text_from_adf(self, adf: dict) -> str:
        text_parts: list[str] = []

        def walk(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    text_parts.append(node.get("text", ""))
                for child in node.get("content", []):
                    walk(child)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(adf)
        return "".join(text_parts)

    def _extract_acceptance_criteria(self, description: str) -> str:
        match = re.search(
            r"Acceptance Criteria[:\s]*(.+?)(?=\n\n|\Z)",
            description,
            re.DOTALL | re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""


