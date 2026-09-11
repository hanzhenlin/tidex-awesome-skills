# Examples

Example packages use `SKILL.example.md` instead of `SKILL.md`. Git-based installers copy the whole root skill directory, and some agents recursively discover every nested `SKILL.md`; the non-discoverable filename keeps examples from becoming active skills after installation. Rename it to `SKILL.md` after copying an example into its own standalone skill directory.

This directory shows complete examples from raw workflow input to final skill package shape.

It is organized in three tiers:

- `simple-note-cleanup`: a small personal workflow
- `team-frontend-review`: a team-level reusable workflow
- `complex-release-orchestrator`: a multi-step, higher-complexity workflow
- `governed-incident-command`: a governed operational asset with lifecycle metadata, review cadence, and evidence reports

Each example contains:

- `raw-workflow.md`: what the user originally gives
- `design-summary.md`: how the meta-skill scopes and structures the result
- `generated-skill/`: the resulting skill package shape

Some examples also include:

- `optimization/`: example-specific baseline descriptions, semantic configs, dev/holdout suites, and route-optimization reports
- `optimization/blind_holdout/`: acceptance prompts used only after the winner is chosen on dev
- `optimization/adversarial/`: harder route-collision prompts used to measure noisy positives, deceptive negatives, and family-level calibration

The complex example is intentionally thicker than the others and includes:

- `manifest.json`
- `input/` and `outputs/` sample artifacts
- `evals/trigger_cases.json`
- richer references and a deterministic script

The governed example adds:

- explicit lifecycle and maturity metadata
- review policy and governed ownership
- reports for maturity and revision history
- context budget evidence
- a stronger example of how reusable skills become maintained assets

Additional evolution example:

- `evolution-frontend-review/`: shows raw workflow, v0, v1, final, and eval delta
