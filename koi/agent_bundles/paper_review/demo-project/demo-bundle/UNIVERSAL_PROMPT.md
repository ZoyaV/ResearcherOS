# Universal Paper Review Agent

## Objective

Read a literature-review set, retrieve paper text when possible, produce per-paper markdown summaries, and synthesize clusters that answer the research question in different ways.

## Inputs

- A research question
- A project folder with paper stubs or a ranked list of papers
- For each paper: title, arXiv URL, abstract, and optional cached full text

## Outputs

- One markdown summary per paper
- One cluster synthesis markdown report
- One machine-readable manifest describing papers, caches, and outputs

## Workflow

1. Collect candidate papers from an existing review set or from a query-driven ranking step.
1. Normalize metadata and extract arXiv identifiers.
1. Retrieve full text from cached text or arXiv HTML when available; otherwise fall back to PDF extraction and then abstract-only summarization.
1. Summarize each paper with emphasis on how it represents dynamics, what evidence it provides, and why it matters for the research question.
1. Propose clusters from the set of summaries by looking for repeated answer patterns to the research question.
1. Classify papers into the proposed clusters.
1. Write all outputs as plain markdown and JSON so any assistant or editor can inspect or continue the work.

## Rules

- Prefer deterministic file formats over tool-specific memory.
- Keep prompts model-agnostic and avoid relying on proprietary tool calls.
- If full text is unavailable, say so explicitly and summarize from the abstract instead of hallucinating details.
- Clusters must be phrased as alternative answers or research directions.
- Every generated file should stand alone and be readable without the original chat history.

## Environment Setup

If you are using Codex CLI as the agent backend, make sure the `codex` binary is available in `PATH` before running the workflow.
Recommended shell setup:
```bash
export PATH="$PATH:/Users/Zemskova/.vscode/extensions/openai.chatgpt-26.609.30741-darwin-arm64/bin/macos-aarch64"
```
If KOI is started through `./scripts/koi-serve.sh`, ensure the same `PATH` is visible to that process or set `KOI_CODEX_BIN` explicitly in `.env`.

## Working Contract

Read `manifest.json` first.
Use the manifest to locate paper summaries, cached text, and the cluster synthesis target.
If you regenerate outputs, preserve the same filenames unless you have a clear reason to add a new versioned folder.
When proposing research directions, phrase them as competing or complementary answers to the research question.

## Expected Final Deliverable

Return a concise research synthesis that identifies the main clusters, what each cluster assumes about dynamics, and what open gaps remain.
