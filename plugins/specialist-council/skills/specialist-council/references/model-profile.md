# Model and effort profile

Generated from `profile.json` by `council.py render`. Do not edit by hand.

Each `specialist-council:council-<role>` plugin agent carries this model and effort in its frontmatter. A personality shifts effort only (never the model), clamped to `xhigh` unless the role preset is already higher. Apply the resolved effort through the Agent tool's per-call `effort` field when the host exposes it; otherwise the frontmatter value applies and the shift is reported as requested only. An explicit user model or effort request overrides this table.

## Tier policy

- **haiku** (`claude-haiku-5-5`): Fast retrieval, scanning, and organization where breadth and speed matter more than deep reasoning.
- **sonnet** (`claude-sonnet-5-5`): Production work with observable checks: implementation, pipelines, writing, design, planning.
- **opus** (`claude-opus-5-5`): Deep analytical or verification work where a wrong derivation silently propagates (mechanics, statistics, validation, debugging, contracts).
- **fable** (`claude-fable-5-1`): Highest-consequence judgment: final adjudication, adversarial security, hard-to-reverse architecture, subtle causal identification.
- **Effort**: low = lookup; medium = routine production; high = analysis with verification; xhigh = adversarial or judging work; max = reserved, only by explicit request.

## Roles

| Role | Model | Effort | Why |
|---|---|---|---|
| arbiter | fable | xhigh | Final evaluation and integration; its errors become the deliverable. |
| architect | fable | high | Decomposition decisions are expensive to reverse. |
| causal-inference-analyst | fable | high | Identification arguments fail subtly and look plausible. |
| security-reviewer | fable | xhigh | Adversarial reasoning; one missed path is costly. |
| analyst | opus | high | Mathematical and statistical derivations. |
| api-designer | opus | high | Public contracts are costly to change. |
| challenger | opus | xhigh | Falsification needs depth to find the smallest real counterexample. |
| constitutive-modeler | opus | high | Material laws and calibration identifiability. |
| controls-engineer | opus | high | Stability and estimation analysis. |
| database-engineer | opus | high | Schemas, transactions, and migrations risk data loss. |
| debugger | opus | high | Root-cause isolation across competing explanations. |
| decision-analyst | opus | high | Option comparison under stated priorities. |
| experimental-design-specialist | opus | high | Choosing discriminating experiments under constraints. |
| failure-mechanics-specialist | opus | high | Failure modes and load paths are safety relevant. |
| fem-specialist | opus | high | Discretization and convergence errors are silent. |
| integration-engineer | opus | medium | Cross-component contracts; mostly checking assembled behavior. |
| interpretability-analyst | opus | high | Model behavior explanations are easy to over-read. |
| materials-specialist | opus | medium | Processing-structure-property reasoning. |
| optimization-specialist | opus | high | Formulation and feasibility proofs. |
| peer-reviewer | opus | high | Whether claims survive scrutiny. |
| reliability-engineer | opus | high | Failure and recovery behavior under degraded conditions. |
| reproducibility-auditor | opus | medium | Tracing raw inputs to results; methodical rather than creative. |
| requirements-analyst | opus | medium | Resolving ambiguity into verifiable scope. |
| rheology-specialist | opus | medium | Flow-curve interpretation and protocol artifacts. |
| scenario-planner | opus | medium | Robustness across plausible futures. |
| statistician | opus | high | Inference, sampling units, and effect sizes. |
| systems-thinker | opus | high | Feedback loops and second-order effects. |
| uncertainty-analyst | opus | high | Sensitivity and propagation reasoning. |
| validation-auditor | opus | high | Leakage and generalization claims need careful audit. |
| accessibility-reviewer | sonnet | medium | Standards-based inclusive-use review. |
| additive-manufacturing-specialist | sonnet | medium | Buildability and toolpath checks. |
| backend-engineer | sonnet | high | Business logic and state transitions with tests. |
| builder | sonnet | medium | General implementation with observable checks. |
| cost-analyst | sonnet | medium | Budget arithmetic and tradeoffs. |
| data-engineer | sonnet | medium | Ingestion and transformations. |
| data-quality-auditor | sonnet | medium | Profiling and fitness checks. |
| designer | sonnet | medium | Interfaces and visuals. |
| editor | sonnet | medium | Prose clarity and synthesis. |
| experimentalist | sonnet | medium | Running and documenting methods. |
| frontend-engineer | sonnet | medium | Client behavior and state. |
| geospatial-analyst | sonnet | medium | Spatial joins and projections. |
| instructional-designer | sonnet | medium | Lesson alignment. |
| literature-reviewer | sonnet | medium | Source gathering and synthesis. |
| metrology-specialist | sonnet | high | Error budgets and calibration arithmetic. |
| ml-engineer | sonnet | high | Training and inference pipelines with baselines. |
| performance-engineer | sonnet | high | Measured bottlenecks, not guesses. |
| presentation-strategist | sonnet | medium | Narrative and slide structure. |
| process-improvement-analyst | sonnet | medium | Workflow bottlenecks. |
| product-strategist | sonnet | medium | Priorities and user value. |
| project-planner | sonnet | medium | Sequencing and milestones. |
| refactoring-engineer | sonnet | medium | Behavior-preserving changes guarded by tests. |
| release-engineer | sonnet | medium | Builds, CI gates, packaging. |
| retrieval-engineer | sonnet | medium | Indexing and retrieval pipelines. |
| scientific-writer | sonnet | high | Claims must match evidence precisely. |
| technical-documentarian | sonnet | medium | Guides and runbooks. |
| test-engineer | sonnet | high | Acceptance and regression coverage. |
| transport-network-analyst | sonnet | high | Graph and assignment semantics. |
| visualization-specialist | sonnet | medium | Charts and figures. |
| information-architect | haiku | medium | Organizing and indexing existing knowledge. |
| scout | haiku | medium | Fast, broad source discovery. |

## Personality effort shifts

| Personality | Shift |
|---|---|
| archivist | -1 |
| conservative-operator | +1 |
| contrarian | +1 |
| detective | +1 |
| empiricist | +0 |
| explorer | +0 |
| futurist | +0 |
| mediator | +0 |
| minimalist | -1 |
| optimizer | +0 |
| perfectionist | +1 |
| pragmatist | -1 |
| skeptic | +1 |
| synthesist | +1 |
| systems-thinker | +0 |
| teacher | +0 |
| theorist | +1 |
| user-advocate | +0 |

## Team presets (resolved)

- **Feature Delivery**: backend-engineer → sonnet/high; frontend-engineer → sonnet/medium; test-engineer → sonnet/high; judge arbiter → fable/xhigh
- **Bug Clinic**: debugger + detective → opus/xhigh; test-engineer + skeptic → sonnet/xhigh; judge arbiter → fable/xhigh
- **Service Readiness**: reliability-engineer → opus/high; security-reviewer → fable/xhigh; performance-engineer → sonnet/high; judge arbiter → fable/xhigh
- **Data Trust**: data-quality-auditor → sonnet/medium; data-engineer → sonnet/medium; statistician → opus/high; judge arbiter → fable/xhigh
- **ML Validation**: validation-auditor + skeptic → opus/xhigh; ml-engineer + pragmatist → sonnet/medium; statistician → opus/high; judge arbiter → fable/xhigh
- **Research Synthesis**: literature-reviewer → sonnet/medium; peer-reviewer → opus/high; scientific-writer → sonnet/high; judge arbiter → fable/xhigh
- **Mechanics Review**: fem-specialist → opus/high; constitutive-modeler → opus/high; experimental-design-specialist → opus/high; judge arbiter → fable/xhigh
- **Printability Lab**: additive-manufacturing-specialist → sonnet/medium; rheology-specialist → opus/medium; validation-auditor → opus/high; judge arbiter → fable/xhigh
- **Network Resilience**: transport-network-analyst → sonnet/high; geospatial-analyst → sonnet/medium; uncertainty-analyst → opus/high; judge arbiter → fable/xhigh
- **Paper Revision**: peer-reviewer + skeptic → opus/xhigh; scientific-writer → sonnet/high; visualization-specialist → sonnet/medium; judge arbiter → fable/xhigh
- **Teach and Explain**: instructional-designer + teacher → sonnet/medium; visualization-specialist → sonnet/medium; challenger → opus/xhigh; judge arbiter → fable/xhigh
- **Decision Room**: decision-analyst → opus/high; cost-analyst → sonnet/medium; scenario-planner → opus/medium; judge arbiter → fable/xhigh
