from __future__ import annotations

import re
from dataclasses import dataclass

REPORT_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
QUERY_RE = re.compile(r"^- Query:\s*(.+?)\s*$", re.MULTILINE)
SCORE_RE = re.compile(r"^- Score:\s*(.+?)\s*$", re.MULTILINE)
ARXIV_RE = re.compile(r"^- ArXiv:\s*(.+?)\s*$", re.MULTILINE)
MATCHED_TERMS_RE = re.compile(r"^- Matched terms:\s*(.+?)\s*$", re.MULTILINE)
ABSTRACT_BLOCK_RE = re.compile(
    r"## Abstract\s+(.*?)(?:\n## |\Z)", re.DOTALL | re.IGNORECASE
)
MAX_TEXT_CHARS = 60000


@dataclass(frozen=True)
class ReviewPaper:
    title: str
    arxiv_url: str
    query: str
    score: float | None
    abstract: str
    matched_terms: tuple[str, ...]
    source_report: str


@dataclass(frozen=True)
class PaperSummary:
    core_idea: str
    representation_of_dynamics: str
    query_answer: str
    answer_strategy_key: str
    answer_strategy_label: str
    answer_evidence: tuple[str, ...]
    evidence: str
    usefulness: str
    limitations: str
    signature_terms: tuple[str, ...]
    citation_sentences: tuple[str, ...]


@dataclass(frozen=True)
class PaperArtifact:
    rank: int
    title: str
    arxiv_url: str
    arxiv_id: str
    year: int | None
    source_report: str
    summary_path: str
    html_path: str | None
    pdf_path: str | None
    text_path: str | None
    extracted_text_chars: int
    used_full_text: bool
    summary_backend: str | None
    cluster_key: str
    cluster_label: str
    query_answer: str
    answer_strategy_key: str
    answer_strategy_label: str
    answer_evidence: tuple[str, ...]
    assignment_rationale: str


@dataclass(frozen=True)
class PaperAnswerArtifact:
    rank: int
    title: str
    arxiv_url: str
    arxiv_id: str
    year: int | None
    source_report: str
    answer_path: str
    html_path: str | None
    pdf_path: str | None
    text_path: str | None
    extracted_text_chars: int
    used_full_text: bool
    answer_backend: str | None
    answer_source: str
    short_answer: str
    comprehensive_answer: str
    evidence: tuple[str, ...]
    limitations: str
    cluster_key: str | None = None
    cluster_label: str | None = None
    cluster_rationale: str | None = None


@dataclass(frozen=True)
class PaperAnswerCluster:
    key: str
    label: str
    answer: str
    rationale: str
    distinguishing_features: str
    signature_terms: tuple[str, ...]
    paper_titles: tuple[str, ...]


@dataclass(frozen=True)
class UniversalAgentSpec:
    name: str
    objective: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    workflow: tuple[str, ...]
    rules: tuple[str, ...]


@dataclass(frozen=True)
class ProposedCluster:
    key: str
    strategy_key: str
    label: str
    answer_hint: str
    answer: str
    direction: str
    signature_terms: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class AnswerStrategy:
    key: str
    label: str
    answer_hint: str
    answer: str
    direction: str
    keywords: tuple[str, ...]


ANSWER_STRATEGIES: tuple[AnswerStrategy, ...] = (
    AnswerStrategy(
        key="temporal_layer",
        label="Temporal Layers And Motion Fields",
        answer_hint="Represent dynamics by adding an explicit temporal or motion layer to the scene graph.",
        answer="A common answer is to extend the scene graph itself with a dedicated dynamics layer that stores motion, flow, or time-aware state on top of the static hierarchy.",
        direction="This cluster is useful when the review should focus on native graph extensions for time, motion flow, or continuous dynamics.",
        keywords=(
            "temporal flow",
            "4d scene graph",
            "dynamics layer",
            "motion flows",
            "continuous motion",
            "continuous directional motion",
            "maps of dynamics",
            "additional dynamics layer",
        ),
    ),
    AnswerStrategy(
        key="state_forecasting",
        label="Temporal State Transitions And Forecasts",
        answer_hint="Represent dynamics as graph state transitions across observed and future time steps.",
        answer="Another answer is to model dynamics as evolving scene graph states, where objects and relations are tracked, linked, or forecast over time.",
        direction="This cluster is useful when the review should emphasize temporal evolution, anticipation, forecasting, or tracklet consistency.",
        keywords=(
            "forecast",
            "future",
            "anticipation",
            "unobserved frames",
            "temporal evolution",
            "tracklet",
            "observed frames",
            "over time",
            "temporal consistency",
        ),
    ),
    AnswerStrategy(
        key="action_effect",
        label="Action-Conditioned Graph Changes",
        answer_hint="Represent dynamics through action-conditioned transitions between scene graph states.",
        answer="Some papers answer the question by treating dynamics as the effect of actions, so the graph changes according to interventions, activities, or predicted action consequences.",
        direction="This cluster is useful when the review should focus on action effects, intervention-driven state change, or explainable action prediction.",
        keywords=(
            "action-effect",
            "effects of actions",
            "action prediction",
            "human activity",
            "described in natural language",
            "pairs of scene-graphs",
            "subject-object relationships",
            "driver-action",
        ),
    ),
    AnswerStrategy(
        key="memory_tracking",
        label="Memory, Tracking, And Persistent Updates",
        answer_hint="Represent dynamics by keeping a persistent scene graph memory that is updated as the world changes.",
        answer="Another answer is to use scene graphs as persistent memory structures, updating nodes and relations over time so the graph remains a current world model.",
        direction="This cluster is useful when the review should focus on online updates, temporal memory, long-term dependencies, or filtered state tracking.",
        keywords=(
            "memory",
            "long-term",
            "persistent",
            "continuously updated",
            "particle filter",
            "state tracking",
            "online",
            "dependency",
            "updates",
        ),
    ),
    AnswerStrategy(
        key="multimodal_fusion",
        label="Multimodal Dynamic Fusion",
        answer_hint="Represent dynamics by fusing scene graphs with complementary temporal signals from multiple modalities.",
        answer="Some papers represent dynamics by combining graph structure with time-varying cues from multiple modalities such as video, audio, language, point clouds, or RGB-D sensing.",
        direction="This cluster is useful when the review should emphasize multimodal evidence fusion for dynamic scene understanding.",
        keywords=(
            "audio-visual",
            "tri-modal",
            "multimodal",
            "point clouds",
            "language",
            "rgb-d",
            "egocentric vision",
            "confluence",
            "sensor",
        ),
    ),
    AnswerStrategy(
        key="planning_semantic_map",
        label="Task-Oriented Semantic Maps",
        answer_hint="Represent dynamics as an updatable semantic world model for planning, grounding, or robot control.",
        answer="Another answer is to use scene graphs as dynamic semantic maps that support planning, grounding, localization, or manipulation in changing environments.",
        direction="This cluster is useful when the review should focus on embodied reasoning, planning, navigation, or task execution over dynamic graphs.",
        keywords=(
            "planning",
            "planner",
            "path",
            "navigation",
            "robot",
            "manipulation",
            "grounding",
            "localization",
            "retrieval",
            "tasks",
        ),
    ),
    AnswerStrategy(
        key="static_relational",
        label="Static Relational Structure",
        answer_hint="Use scene graphs mainly as static relational structure rather than as an explicit model of dynamics.",
        answer="A final group does not directly model scene dynamics; instead, it uses scene graphs as structured relational scaffolds for generation, reasoning, alignment, or evaluation.",
        direction="This cluster is useful when the review should separate truly dynamic representations from papers that only contribute indirect structural lessons.",
        keywords=(
            "generate",
            "generation",
            "synthesis",
            "reasoning",
            "alignment",
            "captioning",
            "visual question answering",
            "structured rubrics",
            "image retrieval",
        ),
    ),
)
ANSWER_STRATEGY_BY_KEY = {strategy.key: strategy for strategy in ANSWER_STRATEGIES}


UNIVERSAL_AGENT_SPEC = UniversalAgentSpec(
    name="Universal Paper Review Agent",
    objective=(
        "Read a literature-review set, retrieve paper text when possible, produce per-paper markdown summaries, "
        "and synthesize clusters that answer the research question in different ways."
    ),
    inputs=(
        "A research question",
        "A project folder with paper stubs or a ranked list of papers",
        "For each paper: title, arXiv URL, abstract, and optional cached full text",
    ),
    outputs=(
        "One markdown summary per paper",
        "One cluster synthesis markdown report",
        "One machine-readable manifest describing papers, caches, and outputs",
    ),
    workflow=(
        "Collect candidate papers from an existing review set or from a query-driven ranking step.",
        "Normalize metadata and extract arXiv identifiers.",
        "Retrieve full text from cached text or arXiv HTML when available; otherwise fall back to PDF extraction and then abstract-only summarization.",
        "Summarize each paper with emphasis on how it represents dynamics, what evidence it provides, and why it matters for the research question.",
        "Propose clusters from the set of summaries by looking for repeated answer patterns to the research question.",
        "Classify papers into the proposed clusters.",
        "Write all outputs as plain markdown and JSON so any assistant or editor can inspect or continue the work.",
    ),
    rules=(
        "Prefer deterministic file formats over tool-specific memory.",
        "Keep prompts model-agnostic and avoid relying on proprietary tool calls.",
        "If full text is unavailable, say so explicitly and summarize from the abstract instead of hallucinating details.",
        "Clusters must be phrased as alternative answers or research directions.",
        "Every generated file should stand alone and be readable without the original chat history.",
    ),
)

PAPER_REVIEW_BUNDLE_KIND = "paper_review"
PAPER_QA_BUNDLE_KIND = "paper_question_answer"
MAX_HTML_CHARS = 120000

