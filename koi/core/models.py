"""Domain model for hypothesis trees and experiment kanbans."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    PROBLEM = "problem"
    CAUSE = "cause"
    CAUSE_EVIDENCE = "cause_evidence"
    REMEDIATION = "remediation"
    METHOD = "method"
    EXPERIMENT = "experiment"  # legacy tree leaf; experiments live on method kanbans


# Which child types are allowed under each parent type.
ALLOWED_CHILDREN: dict[Optional[NodeType], list[NodeType]] = {
    None: [NodeType.PROBLEM],
    NodeType.PROBLEM: [NodeType.CAUSE],
    NodeType.CAUSE: [NodeType.CAUSE_EVIDENCE, NodeType.REMEDIATION],
    NodeType.CAUSE_EVIDENCE: [NodeType.METHOD],
    NodeType.REMEDIATION: [NodeType.METHOD],
    NodeType.METHOD: [],
    NodeType.EXPERIMENT: [],
}

# Node types that own a kanban board for experiments.
KANBAN_OWNER_TYPES = {NodeType.METHOD}


class Verdict(str, Enum):
    OPEN = "open"
    SUPPORTED = "supported"
    REFUTED = "refuted"


class ResearchQuestionCertainty(str, Enum):
    """Whether experiment results answer the question precisely."""

    DEFINITE = "definite"
    TENTATIVE = "tentative"


class MethodResearchQuestion(BaseModel):
    id: str = Field(default_factory=lambda: f"rq-{uuid4().hex[:8]}")
    question: str
    answer: str = ""  # concise technical summary (not shown in the UI)
    narrative: str = ""  # readable answer shown in the modal
    certainty: ResearchQuestionCertainty = ResearchQuestionCertainty.DEFINITE
    importance: int = Field(default=3, ge=1, le=5)  # relative importance
    card_id: Optional[str] = None  # source kanban ExperimentCard.id


class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    parent_id: Optional[str] = None
    node_type: NodeType
    title: str
    description: str = ""
    verdict: Verdict = Verdict.OPEN
    research_questions: list[MethodResearchQuestion] = Field(default_factory=list)


class KanbanColumn(BaseModel):
    id: str
    title: str
    order: int


class ExperimentCard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    board_id: str
    column_id: str
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)  # prerequisite card ids (DAG edges)
    linked_node_id: Optional[str] = None  # optional link to a tree experiment node
    created_at: Optional[str] = None  # ISO-8601 UTC, set on create
    updated_at: Optional[str] = None  # ISO-8601 UTC, bumped on every card update


class KanbanBoard(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner_node_id: str
    columns: list[KanbanColumn] = Field(default_factory=list)
    cards: list[ExperimentCard] = Field(default_factory=list)


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    literature_keywords: list[str] = Field(default_factory=list)
    card_tags: list[str] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    boards: list[KanbanBoard] = Field(default_factory=list)


DEFAULT_KANBAN_COLUMNS = [
    KanbanColumn(id="backlog", title="Backlog", order=0),
    KanbanColumn(id="running", title="Running", order=1),
    KanbanColumn(id="done", title="Done", order=2),
    KanbanColumn(id="successful", title="Successful", order=3),
]

KANBAN_CONCLUSION_COLUMN_IDS = frozenset({"done", "successful"})

LEGACY_COLUMN_PLANNED = "planned"
