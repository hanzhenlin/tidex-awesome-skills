# Benchmark Reproducibility

Generated at: `2026-08-17`
Commit: `4f77b8a6ee7e59284219d0adcbbceef4dcdcdca9`
Working tree dirty at generation: `true`
Source tree dirty at generation: `false`
Generated evidence dirty at generation: `true`
Evidence bundle SHA256: `ec52890423f7cb86c63078e55f4df33df8728efe5f84807902ba8b178fa436dd`

## Summary

- reproducibility ready: `true`
- release lock ready: `true`
- methodology complete: `true`
- required artifacts: `25`
- missing artifacts: `0`
- source contract sha256: `54d1fb49b5de`
- archive sha256: `f5275f7471c0`
- output cases: `5`
- disclosed failure cases: `3`
- reproduction commands: `23`
- provider evidence complete: `true`
- phase-one provider matrix complete: `true`
- phase-one three-reviewer adjudication complete: `true`
- phase-one quality promotion complete: `true`
- human review complete: `false`
- world-class ready: `false`
- world-class source checks: `11` pass / `14` total; `3` blocked
- beta test ready: `true`
- beta test blockers: `0`
- beta deferred evidence: `4`
- public claim ready: `false`
- public claim blockers: `3`
- changed files at generation: `24`
- source changed files at generation: `0`
- generated changed files at generation: `24`

This report proves local benchmark reproducibility only. It keeps external provider and human-review gaps visible instead of counting them as complete. The git commit and dirty samples are generation-time context; the evidence bundle SHA is the durable anchor for the artifacts listed below.

## Beta Test Boundary

- ready: `true`
- scope: beta/public test release without superiority, fully-reviewed, or world-class claims
- policy: Human blind-review, native permission enforcement, real client telemetry, and ledger acceptance may be deferred for beta/public testing, but public claims must remain blocked until those evidence entries are accepted.
- required wording: Use beta, public test, or technical preview wording; do not claim world-class readiness, fully reviewed quality, or proven superiority over baseline.

| Blocker |
| --- |
| none |

| Deferred evidence | Reason |
| --- | --- |
| `provider-holdout` | Provider-backed source evidence exists, but formal ledger submission and reviewer acceptance are still pending before public claims. |
| `human-adjudication` | Human adjudication evidence is still pending; deferred for beta/public testing and still required before superiority, fully-reviewed, or world-class claims. |
| `native-permission-enforcement` | Native enforcement proof is still pending; deferred for beta/public testing and still required before world-class claims. |
| `native-client-telemetry` | Real client telemetry is still pending; deferred for beta/public testing and still required before world-class claims. |

## Public Claim Boundary

- ready: `false`
- scope: public benchmark or world-class readiness claim
- policy: Local reproducibility can pass before public claims; public claims require provider evidence, human adjudication, clean release lock, accepted world-class evidence, and complete source checks.

| Blocker |
| --- |
| human blind-review adjudication is incomplete |
| world-class evidence is not accepted yet (2 open gaps, 4 ledger pending) |
| world-class source checks are not all accepted (11/14 pass, 3 blocked) |

## Release Lock

- ready: `true`
- reason: only generated evidence artifacts were dirty at generation time
- status scope: generation-time status before this report is written

## Evidence Bundle

- algorithm: `sha256(path,label,exists,artifact_sha256)`
- artifacts: `25` / `25`
- sha256: `ec52890423f7cb86c63078e55f4df33df8728efe5f84807902ba8b178fa436dd`

## Methodology Sections

| Section | Status |
| --- | --- |
| `## Benchmark Types` | present |
| `## Sample Sources` | present |
| `## Evaluation Dimensions` | present |
| `## Weighting Rule` | present |
| `## Failure Disclosure` | present |
| `## Reproduction` | present |

## Required Artifacts

| Label | Path | Status | SHA256 |
| --- | --- | --- | --- |
| methodology | `reports/benchmark_methodology.md` | present | `57025e0123ce` |
| failure_disclosure | `evals/failure-cases.md` | present | `28833c0d4a21` |
| output_cases | `evals/output/cases.jsonl` | present | `a6ae96857116` |
| output_schema | `evals/output/schema.json` | present | `f2812b6b6655` |
| output_scorecard | `reports/output_quality_scorecard.json` | present | `0806258a8e08` |
| output_execution | `reports/output_execution_runs.json` | present | `4df66b63d2e7` |
| blind_review | `reports/output_blind_review_pack.json` | present | `bbe2db8ec277` |
| review_adjudication | `reports/output_review_adjudication.json` | present | `510fc207bf20` |
| trigger_scorecard | `reports/route_scorecard.json` | present | `06d7ad6eb002` |
| runtime_conformance | `reports/conformance_matrix.json` | present | `de8093861e68` |
| trust_report | `reports/security_trust_report.json` | present | `b5d459f5be1a` |
| python_compatibility | `reports/python_compatibility.json` | present | `195e3f822f6f` |
| registry_audit | `reports/registry_audit.json` | present | `adbd9e56a47a` |
| package_verification | `reports/package_verification.json` | present | `15cd1826ede3` |
| install_simulation | `reports/install_simulation.json` | present | `8def0abf208a` |
| skill_os2_audit | `reports/skill_os2_audit.json` | present | `14a436c5b835` |
| world_class_evidence_plan | `reports/world_class_evidence_plan.json` | present | `f283c5487869` |
| world_class_evidence_ledger | `reports/world_class_evidence_ledger.json` | present | `0a085d12960e` |
| world_class_evidence_intake | `reports/world_class_evidence_intake.json` | present | `fd6cce982d53` |
| world_class_evidence_preflight | `reports/world_class_evidence_preflight.json` | present | `a82935a49218` |
| world_class_submission_review | `reports/world_class_submission_review.json` | present | `08c79e264513` |
| world_class_operator_runbook | `reports/world_class_operator_runbook.json` | present | `3734f7f2dacb` |
| world_class_operator_runbook_markdown | `reports/world_class_operator_runbook.md` | present | `05620822172d` |
| world_class_operator_runbook_html | `reports/world_class_operator_runbook.html` | present | `d74c2c7a918d` |
| world_class_claim_guard | `reports/world_class_claim_guard.json` | present | `251d3d487308` |

## Reproduction Commands

- `git rev-parse HEAD`
  - evidence: `git commit hash`
- `make eval-suite`
  - evidence: `reports/eval_suite.json`
- `python3 scripts/yao.py output-eval --self`
  - evidence: `reports/output_quality_scorecard.json`
- `python3 scripts/yao.py output-exec --runner-command '["python3","scripts/local_output_eval_runner.py"]' --self`
  - evidence: `reports/output_execution_runs.json`
- `python3 scripts/yao.py output-review --self`
  - evidence: `reports/output_review_adjudication.json`
- `python3 scripts/yao.py skill-ir . --output-json skill-ir/examples/yao-meta-skill.json --self`
  - evidence: `skill-ir/examples/yao-meta-skill.json`
- `python3 scripts/yao.py conformance . --self`
  - evidence: `reports/conformance_matrix.json`
- `python3 scripts/yao.py trust . --self`
  - evidence: `reports/security_trust_report.json`
- `python3 scripts/yao.py python-compat . --self`
  - evidence: `reports/python_compatibility.json`
- `python3 scripts/yao.py package . --platform openai --platform claude --platform generic --platform vscode --expectations evals/packaging_expectations.json --output-dir dist --zip --self`
  - evidence: `dist/yao-meta-skill.zip`
- `python3 scripts/yao.py package-verify . --package-dir dist --require-zip --self`
  - evidence: `reports/package_verification.json`
- `python3 scripts/yao.py install-simulate . --package-dir dist --self`
  - evidence: `reports/install_simulation.json`
- `python3 scripts/yao.py registry-audit . --self`
  - evidence: `reports/registry_audit.json`
- `python3 scripts/yao.py skill-os2-audit . --self`
  - evidence: `reports/skill_os2_audit.json`
- `python3 scripts/yao.py world-class-evidence . --self`
  - evidence: `reports/world_class_evidence_plan.json`
- `python3 scripts/yao.py world-class-ledger . --submissions-dir evidence/world_class/submissions --self`
  - evidence: `reports/world_class_evidence_ledger.json`
- `python3 scripts/yao.py world-class-intake . --submissions-dir evidence/world_class/submissions --self`
  - evidence: `reports/world_class_evidence_intake.json`
- `python3 scripts/yao.py world-class-preflight . --submissions-dir evidence/world_class/submissions --self`
  - evidence: `reports/world_class_evidence_preflight.json`
- `python3 scripts/yao.py world-class-submission-review . --submissions-dir evidence/world_class/submissions --self`
  - evidence: `reports/world_class_submission_review.json`
- `python3 scripts/yao.py world-class-runbook . --submissions-dir evidence/world_class/submissions --self`
  - evidence: `reports/world_class_operator_runbook.json`
- `python3 scripts/yao.py world-class-claim-guard . --self`
  - evidence: `reports/world_class_claim_guard.json`
- `python3 scripts/yao.py evidence-consistency . --self`
  - evidence: `reports/evidence_consistency.json`
- `make ci-test`
  - evidence: `CI target output`

## Failure Disclosure

- path: `evals/failure-cases.md`
- disclosed cases: `3`
- policy: Keep representative failures visible and tied to regression checks.

## Limits

- The git commit and dirty flags are generation-time context; release lock is blocked by source changes, while generated evidence artifacts are tracked separately.
- Provider-backed model holdout source evidence is complete, but ledger acceptance still requires a valid independently reviewed submission packet.
- Pending blind-review decisions are visible but do not count as human adjudication.
- World-class readiness remains false until external and human evidence gaps close.
- Beta/public testing may proceed without human blind-review only when wording avoids superiority, fully-reviewed, or world-class claims.
