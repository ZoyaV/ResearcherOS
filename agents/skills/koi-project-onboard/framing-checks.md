# Framing checks: node ontology and interview frames

Companion to [SKILL.md](SKILL.md). Apply these checks when fixing each
Socratic layer and again before writing `project.md`.

The KOI hierarchy is strict:

```text
problem → cause → (cause_evidence | remediation) → method → kanban cards
```

Verdicts (`supported`, `refuted`, `open`) belong to **cause**, not method.

## Node meaning during the interview

The tree is a causal research argument, not a topic/task list.

| Node | What it records | Control question |
|------|-----------------|------------------|
| `problem` | Observable phenomenon or gap: object, conditions, actual/expected outcome, significance | What requires explanation? |
| `cause` | Explanatory hypothesis: the mechanism believed to produce the problem | Why does it happen? |
| `cause_evidence` | Testable prediction that should be observed if the cause is true | What would we see under the proposed cause? |
| `remediation` | Intervention hypothesis: a change expected to weaken the cause and problem | What changes, and what effect should follow? |
| `method` | Protocol testing its parent: comparison, control, measurement, decision rule | How do we distinguish support from contradiction? |
| kanban card | Concrete unit of a method: run, collection, analysis, or ablation | What work unit happens now? |

A `cause` is already an explanatory hypothesis. In onboarding, “hypothesis”
refers to its two testable child forms: `cause_evidence` and `remediation`.

`cause_evidence` is not completed evidence and not a command such as “inspect
logs.” It is an expected observation stated **before** evaluation. Actual results
belong in card reports.

A remediation must express:

```text
intervention → change in cause → change in problem
```

Failure of one remediation refutes that intervention but does not automatically
refute the cause.

## Type checks

Run every draft node through these tests. A failure means rewrite, not “keep it
as a topic.”

| # | Test | Question | Common failure |
|---|------|----------|----------------|
| 1 | Phenomenon vs theory | Is this an observed gap, or already an explanation? | Problem = “poor exploration” (a cause) |
| 2 | Causal vs instrumental | Does cause explain why, or propose trying X? | Cause = “add diversity bonus” |
| 3 | Falsifiability | What would refute the cause? | “Study X's effect” without direction |
| 4 | Intervention link | Does remediation act on the named cause? | Reward hypothesis under a “too little data” cause |
| 5 | Evidence vs fix | Diagnose (`cause_evidence`) or intervene (`remediation`)? | Diagnostic ablation recorded as remediation |
| 6 | Grain size | Can one verdict resolve this node? | “All OOD generalization problems” |
| 7 | Underdetermination | Does one node mix several causes? | Shift + capacity + reward in one cause |
| 8 | Method is protocol | Does method name comparison and metric rather than an idea? | Method = “diversity” without baseline |
| 9 | Prediction vs procedure | Is evidence an expected observation rather than a command? | “Inspect logs” |
| 10 | Prediction vs result | Was evidence stated before evaluation? | “Diversity was low” before a run |
| 11 | Parent link | Does the child test its actual parent? | Reward remediation under a data-volume cause |
| 12 | Decision completeness | Are supporting and contradicting outcomes clear? | Metric without direction or threshold |

Code and literature are evidence, not automatic answers:

| Label | Meaning | Use |
|-------|---------|-----|
| `code+lit` | Supported by repository and literature | Preferred frame |
| `code-only` | A bet in code with weak literature support | Fine for remediation/method |
| `lit-only` | Common field frame with no code support | Use cautiously; do not make it the root without confirmation |

Never replace the problem with a method, model, loss, or job-script name.

## Node readiness gates

Question count does not close a layer. A node is ready only when every mandatory
gate passes. On `FAIL`, continue the interview.

### problem

- Object/system is clear.
- The observed phenomenon is specific rather than a broad topic.
- Conditions where it appears are named.
- Actual versus expected state or comparison is clear.
- Scientific or practical significance is explained.
- The wording contains no assumed cause, method, or solution.

### cause

- One mechanism, not a restated problem or a list of alternatives.
- Explains how it produces the parent problem.
- A world claim, not “add / try / study X.”
- At least one outcome would make us abandon it.
- One meaningful verdict can resolve it.

### cause_evidence

- States the expected observation if the cause is true.
- Explains why that observation follows from the parent cause.
- Names a contradicting observation.
- Is not a protocol, completed result, or intervention.

### remediation

- Names a concrete intervention.
- Says which part of the parent cause it changes.
- States the expected intermediate effect on the cause.
- States the expected effect on the problem.
- Makes clear that intervention failure need not refute the cause.

### method

- Identifies the parent cause_evidence/remediation being tested.
- Defines the intervention or comparison conditions.
- Defines baseline/control and fixed conditions.
- Names data/environment/sample and primary measurements.
- Prespecifies supporting and contradicting outcomes.
- Is reproducible, not a model/feature/topic name.

### Branch coherence

Read the branch as one argument:

```text
We observe the problem
because we hypothesize the cause;
if the cause is true, we expect cause_evidence
and/or remediation should weaken the cause;
the method distinguishes the expected outcomes.
```

If it breaks, identify the weak edge and continue interviewing even when the
individual nodes look good.

## Persistent adaptive interview

The researcher supplies domain meaning; the agent owns node classification,
testability, and tree coherence. Do not accept the researcher's node label
without checking it.

After every answer:

1. Paraphrase without KOI terminology.
2. Classify the substance as phenomenon, mechanism, prediction, intervention,
   protocol, or completed result.
3. Check current-node gates and parent linkage.
4. Select the single most important defect or gap.
5. Explain briefly why the current wording cannot be fixed yet.
6. Offer 1–3 plausible interpretations grounded in literature, code, or earlier answers.
7. Ask exactly one question that closes the gap or distinguishes interpretations.
8. Repeat until `PASS`, then propose final wording for confirmation.

Do not repeat mechanically. Every follow-up must use the previous answer and
target a specific missing component.

### Short answer

“Poor generalization” is a topic, not a ready problem. Ask which conditions show
the gap (training vs unseen environments, short vs long episodes, or task
classes), then ask for the missing observable change, expectation, or importance.

### Misclassified answer

If the user says “the cause is to add memory,” recognize a remediation and ask
which current failure the memory should repair: loss of early events, insufficient
context, or failure to use stored information.

If “the evidence is compare with and without memory,” recognize a method and ask
which difference should appear if lost early context is the cause.

If the problem is “the agent forgets early events,” test whether this is actually
a cause by asking which externally observable behavior it explains.

### Academic pushback formula

```text
What I heard → failed criterion → why it matters to the branch
→ 1–3 plausible interpretations → one distinguishing question
```

Do not agree out of politeness and do not merely say “wrong node type.” Explain
the conceptual boundary and help improve the framing. Never invent domain facts
without confirmation.

## Prose and anti-jargon

Every onboarding message follows
[`koi-prose-style`](../koi-prose-style/SKILL.md): self-check before each message
and a full subagent cycle when fixing a layer and before writing files.

| Bad | Good |
|-----|------|
| Executable code world model fails trace validation | World model fails to reproduce game transitions from a recorded playthrough |
| validate fail on CWM rollout | Transition checks fail when replaying the recorded trajectory |
| OOD SR drop after GiGPO LoRA | After reinforcement learning, successful episodes decrease outside the training distribution |
| diversity_coef / SR@50 hybrid | Mixed reward combines episode success and action-variety bonus; evaluation measures success at step 50 |
| trace mismatch in env step | Predicted next frame does not match the actual game transition |

Automatic `FAIL`:

1. Unexplained jargon in a node title.
2. Module/file/flag/pipeline status in a title (`validate fail`, `OOM`, `WIP`).
3. Languages mixed within one phrase.
4. A reader without the repository cannot identify the phenomenon.

Keep technical paths and class names in card `desc` or internal agent notes, not
problem/cause titles.

## Socratic layers

Do not show a “choose Frame A/B/C” table. The variant bank is internal; the
conversation combines prior work, researcher position, and repository evidence.

| Layer | Minimum questions | Output |
|-------|-------------------|--------|
| **PROBLEM** | At least 4 | One problem grounded in researcher position and literature |
| **PROGRAM** | At least 1; 2 for a new program | `programs:` or explicit no-program decision |
| **CAUSE+HYP** | At least 4 | 1–2 causes and 1–2 hypotheses |
| **METHOD** | At least 3 | 1–2 methods and 0–3 seed cards |

Minimum count is a lower bound only. Continue until readiness gates pass.

Before PROGRAM, scan adjacent `*/koi-structure/project.md` files for existing
programs. Ask whether the project joins one. Otherwise propose 2–3 field-level
programs from literature or let the user name one. Program titles use at most
eight words.

Maintain an internal bank:

```text
problem_candidates: [ … ]   # code+lit / lit-only
cause_candidates:   [ … ]
hyp_candidates:     [ … ]   # remediation / cause_evidence
method_candidates:  [ … ]
```

During PROBLEM, expose only problem candidates and papers about the phenomenon.

### Triangulation after each answer

In connected prose, relate:

1. one to three papers and how they frame the phenomenon/cause;
2. a plain academic paraphrase of the user's position;
3. what the repository already measures or changes.

Do not use log-like field labels. A good paragraph says: “You describe … . This
resembles Title (Year), which … . It differs from Author et al. (Year) because
… . In the repository, the distinction appears in … . This suggests framing the
problem as … .” Then ask one question.

Use academic research-interview language, not coaching language:

| Avoid | Prefer |
|-------|--------|
| What hurts most? | Related work frames the problem as A or B. Is your problem similar? |
| How do you feel about it? | Why is this problem worth solving; which field gap does it close? |
| What matters personally? | How would resolving it advance the field? |
| Explain without modules | Under which conditions is the lack of progress clearest? |

## Title limits

| Field | Limit | Put details in |
|-------|-------|----------------|
| Node title | At most 8 words | Node description |
| Kanban card title | At most 8 words | `desc` |
| Project frontmatter title | Prefer at most 8 words | `description` |
| Critical title after two clarity-loop failures | At most 12 words, rarely | Description |

During the clarity loop, the cold reader sees titles only. Before every rewrite,
the Writer rereads `koi-structure/onboard-brief.md`. Do not “clarify” by drifting
from a scientific phenomenon to pipeline debugging. Discard a drifting candidate
even if the cold reader marks it CLEAR.

## Good and bad formulations

### problem

| Bad | Good title | Description |
|-----|------------|-------------|
| Diversity bonus in PPO | Policy fails in unseen environments | After training in one environment, success falls outside the training distribution. |
| CrafText training | Behavior fails under new rules | The agent follows training instructions but cannot transfer its policy to tasks with different rules. |
| Executable code world model validate fail | Model fails to reproduce game rules | Given a recorded game, transition and rule validation fails. |

### cause

| Bad | Good title | Description |
|-----|------------|-------------|
| Need diversity reward | Policy collapses to narrow trajectories | The agent explores too little and repeats a small action set. |
| Try curriculum | Incorrect model of environment rules | The system overestimates which rules determine success. |

A cause description may include refutation: “refuted if behavior remains diverse
at the same budget while out-of-distribution quality still falls.”

### remediation / cause_evidence

| Bad | Good title | Description |
|-----|------------|-------------|
| Research diversity | Reward action variety | An additional incentive should expand explored behavior. |
| Inspect logs | Collapse appears as low action variety | Under the cause, distinct state-action pairs should decrease during training. |

### method

| Bad | Good title | Description |
|-----|------------|-------------|
| Diversity | Variety bonus versus episode success | Compare training with a variety bonus against success-only reward using the same model and budget. |
| Environment experiments | Random versus predictable environments | Compare random action outcomes with a predictable environment using exploration depth and success rate. |

## Final self-check

For every node:

1. All applicable type checks pass.
2. Parent/child types follow the hierarchy.
3. Remediation acts on this cause, not a neighboring cause.
4. Method can become a baseline experiment card in one paragraph.
5. No node is merely a repository filename.
6. `koi-prose-style` passed or the user explicitly waived it after three failures.
7. Title reads naturally without knowing repository classes or flags.
8. Node/card title is at most eight words unless a valid clarity exception exists.
9. Readiness gates pass.
10. The branch reads as one coherent causal argument.
