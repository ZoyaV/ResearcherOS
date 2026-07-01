"""Pydantic request/response bodies for the HTTP API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from koi.core.models import NodeType, ResearchQuestionCertainty


class CreateProjectBody(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    tag: str = Field(min_length=1, max_length=48)
    program_id: Optional[str] = None
    program_title: Optional[str] = None


class CreateProgramBody(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""


class CreateNodeBody(BaseModel):
    parent_id: str
    node_type: NodeType
    title: str = Field(min_length=1)
    description: str = ""


class ResearchQuestionBody(BaseModel):
    id: Optional[str] = None
    question: str = Field(min_length=1)
    answer: str = ""
    narrative: str = ""
    certainty: ResearchQuestionCertainty = ResearchQuestionCertainty.DEFINITE
    importance: int = Field(default=3, ge=1, le=5)
    card_id: Optional[str] = None


class UpdateNodeBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    research_questions: Optional[list[ResearchQuestionBody]] = None


class UpdateCardBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    column_id: Optional[str] = None


class CreateCardBody(BaseModel):
    column_id: str = "backlog"
    title: str = Field(min_length=1)
    description: str = ""


class CardReportBody(BaseModel):
    content: str = ""


class BoardPayload(BaseModel):
    id: str
    owner_node_id: str
    columns: list
    cards: list


class LiteratureSearchBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class LibraryDiscoverBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


class ReviewSetBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    papers: list[dict] = Field(default_factory=list)


class ProjectPaperReviewBody(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    papers: list[dict] = Field(default_factory=list)


class ReviewAgentBody(BaseModel):
    query: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=50)
    refresh: bool = False
    download_pdfs: bool = True
    papers: list[dict] = Field(default_factory=list)


class PaperQuestionAgentBody(BaseModel):
    question: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)
    refresh: bool = False
    download_pdfs: bool = True
    papers: list[dict] = Field(default_factory=list)


class RelatedWorksAnswerBody(BaseModel):
    markdown: str = Field(min_length=1)


class RelatedWorksBody(BaseModel):
    problem: str = Field(min_length=1)
    cluster_keys: list[str] = Field(default_factory=list)


class TranslateToEnglishBody(BaseModel):
    text: str = Field(min_length=1)


class AgentChatBody(BaseModel):
    project_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    method_id: Optional[str] = None
    node_id: Optional[str] = None


class AgentChatAnswerBody(BaseModel):
    answer: str = Field(min_length=1)


class CursorApiKeyBody(BaseModel):
    cursor_api_key: str = ""


class AgentChatSettingsBody(BaseModel):
    agent_chat_mode: Optional[str] = None
    cursor_api_key: Optional[str] = None


class InboxConfiguredBody(BaseModel):
    configured: bool = True
    inbox_kind: str = "chat"
