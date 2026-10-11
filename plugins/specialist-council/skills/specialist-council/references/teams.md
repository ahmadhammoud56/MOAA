# Team selection and recipes

Each recipe member below already has a preset model and effort; personality overlays shift effort. The resolved settings for every recipe, plus the Arbiter judge, are listed in [model-profile.md](model-profile.md#team-presets-resolved). Use them unless the user overrides.

Choose a small team that covers the deliverable and its main uncertainty. These recipes are starting points, not mandatory agents or extra execution permission. The parent is normally the Arbiter. Start with 2 to 3 workers, count an independent judge against live capacity, and use waves only when needed. A large catalog does not justify a large run.

| Recipe | Suggested workers | Distinct contributions and handoff |
|---|---|---|
| Feature Delivery | Backend Engineer, Frontend Engineer, Test Engineer | Server and client own disjoint implementation areas under an agreed contract; tests target acceptance behavior. Add an Integration Engineer only for substantial cross-component work. |
| Bug Clinic | Debugger + Detective, Test Engineer + Skeptic | Isolate the cause and independently reproduce the contract violation; verify the final fix after integration. |
| Service Readiness | Reliability Engineer, Security Reviewer, Performance Engineer | Examine recovery, reachable abuse paths, and measured bottlenecks separately. Apply only relevant review scopes. |
| Data Trust | Data Quality Auditor, Data Engineer, Statistician | Audit raw inputs, trace transformations, and check whether the resulting analysis answers the intended question. |
| ML Validation | Validation Auditor + Skeptic, ML Engineer + Pragmatist, Statistician | Audit evaluation boundaries, propose a workable pipeline, and check sampling units and uncertainty. Agree on the generalization target. |
| Research Synthesis | Literature Reviewer, Peer Reviewer, Scientific Writer | Gather evidence and assess validity independently from raw sources; drafting consumes their completed outputs. A dependent drafting stage waits. |
| Mechanics Review | FEM Specialist, Constitutive Modeler, Experimental Design Specialist | Check numerical setup, physical law/calibration, and discriminating validation experiments. Assign a common mechanism and loading brief. |
| Printability Lab | Additive Manufacturing Specialist, Rheology Specialist, Validation Auditor | Assess deposition/buildability, measurement/material-state interpretation, and prediction generalization. Route measurement uncertainty to Metrology when it dominates. |
| Network Resilience | Transport Network Analyst, Geospatial Analyst, Uncertainty Analyst | Check graph/assignment semantics, spatial operations, and robustness across assumptions. Share scenario definitions. |
| Paper Revision | Peer Reviewer + Skeptic, Scientific Writer, Visualization Specialist | Prioritize scientific concerns, revise supported claims, and correct figures. Writing and figure updates wait for any decisions that change them. |
| Teach and Explain | Instructional Designer + Teacher, Visualization Specialist, Challenger | Align objectives and examples, design accurate visuals, and identify misconceptions. Challenger supplies concrete learner errors. |
| Decision Room | Decision Analyst, Cost Analyst, Scenario Planner | Compare options, verify cost assumptions, and test robustness to changing conditions. Use one shared criteria set. |

## Routing ties and overlap

- Use a narrow specialist when its method is central; use a generalist when the task crosses domains. A Statistician owns inference, a Validation Auditor owns evaluation boundaries, and an ML Engineer owns the workable predictive pipeline. Do not give all three the same vague instruction to analyze the data in split mode.
- Use Experimental Design for selecting informative runs, Metrology for measurement validity, Constitutive Modeling for material laws, and FEM for the numerical approximation. A model that matches measurements may still have identification or discretization problems.
- Use Literature Reviewer for finding and synthesizing studies, Peer Reviewer for whether claims survive scrutiny, Scientific Writer for the manuscript argument, and Editor for broad prose polish.
- Use Architect for system decomposition, API Designer for a concrete interface, and Integration Engineer for checking the assembled interaction. A recipe spanning these jobs may need sequential stages.
- If several roles would return substantially the same artifact, merge responsibilities or use ensemble mode deliberately. Distinguish complementary workers by their outputs and independent candidates by their methods.
- If the task needs an unlisted domain, adapt the closest role or compose a new one with a bounded responsibility and evidence test. Do not misrepresent a familiar title as unavailable expertise or a newly trained model.

## Selection procedure

First map deliverables and decisive uncertainties to candidate roles. Remove redundant responsibilities, retain any named user choices where feasible, and fit the team to capacity and budget. Read only the relevant role cards and personality entries. State why each selected specialist contributes something distinct. When no actual work is requested, show this selection without spawning.

In split mode, identify prerequisites and agree on interfaces before independent writes. Do not assign dependent work as if it can start immediately. In ensemble mode, keep the full deliverable and evidence packet the same, vary methods, and freeze initial candidates before review. In hybrid mode, limit redundant independent work to the consequential uncertain component.

Examples of natural requests:

- Use the ML Validation team with a skeptical Validation Auditor and a pragmatic ML Engineer.
- Give me two independent FEM Specialists, one Theorist and one Empiricist, with an impartial judge.
- Use Feature Delivery, but keep it to two workers and let the parent check integration.
- Show the engineering specialists and their personalities without running them.

## Design provenance and boundaries

Ruflo's [agent directory](https://github.com/ruvnet/ruflo/tree/main/.claude/agents) groups agents into domains such as development, architecture, testing, security, and coordination. Use that broad catalog-and-routing idea as inspiration. The cards and styles here are original definitions for this council. This skill does not install Ruflo, import its agent prompts, or provide its separate memory, learning, federation, or model-provider infrastructure. Existing runtime and adjudication rules remain authoritative for execution.
