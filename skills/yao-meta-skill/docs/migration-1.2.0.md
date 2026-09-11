# Migration to 1.2.0

Version 1.2.0 introduces the first-phase trusted generation core. The release adds transactional evidence publication, canonical Skill IR resolution, a fixed DeepSeek output-evaluation matrix, a frozen trigger holdout, and tighter initial-context gates.

See the [1.2.0 release candidate notes](release-notes-1.2.0.md) for the user-facing change summary and the [Phase 1 visual report](../reports/phase1-trusted-generation-visual-report-v2.html) for the engineering evidence snapshot.

## Required migration steps

1. Add `skill_ir_source` to `manifest.json`. Point it to the Skill's canonical IR JSON. The resolver order is manifest declaration, name-matched `reports/skill-ir.json`, then `skill-ir/examples/<name>.json`. Wildcard example discovery is no longer supported.
2. Generate evidence with `python3 scripts/yao.py evidence-build <skill_dir>`. Dry run remains the default. Commit source and generated reports, confirm a clean worktree, then add `--publish`.
3. Treat `reports/.current-run.json` and `reports/artifact-index.json` as the canonical evidence entrypoint. Keep `.yao/runs` and `.yao/releases` local.
4. Preserve `.yao/publish-transaction.json` and `.yao/publish-snapshots` after an interrupted publish. A dry run returns `recovery-required`. Run `evidence-build <skill_dir> --recover` to restore the previous immutable release or the first-publish snapshot. Resolve integrity errors before starting another publish.
5. For the phase-one provider evaluation, provide `DEEPSEEK_API_KEY` through the environment. The committed matrix fixes DeepSeek V4 Flash and V4 Pro, non-thinking mode, temperature 0, 3,000 maximum output tokens, 40 calls, 250,000 total tokens, and a 60-second timeout.
6. Keep provider answer text under `.yao/runs/<run-id>/raw-outputs`. Reviewers use role-neutral copies under `.yao/runs/<run-id>/review-materials`. The private answer key remains under `.yao/runs/<run-id>/private`; published evidence carries only commitments, metadata, hashes, and redacted summaries.
7. Complete all 20 randomized A/B pairs independently as Reviewer A, B, and C through controlled submissions. Finalize the exact source run with `evidence-finalize-review` and a reviewer registry that binds all three packet hashes. Internal quality promotion requires 15/20 with-skill wins, at least 7/10 for each model, zero critical failures, and Fleiss' kappa of at least 0.40.
8. Packages exclude archive-checksum consumers from the payload checksum scope and add a portable report index. Local install synchronization checks the archive SHA256 against `reports/package_verification.json`, copies those exact bytes, and checks the installed evidence through the portable index. Sync targets preserve the attested archive and require packaging plus verification to run first.
9. Keep the world-class evidence ledger pending until its separate human and external acceptance contracts are complete.

## Trigger and context contract

The 1.2.0 trigger boundary is frozen in `evals/blind_holdout/trigger_cases_v2.json` and protected by its SHA-256 lock. The gate requires precision of at least 0.95, recall of at least 0.90, zero hard-negative false positives, and no regression across the existing 66 cases.

The root `SKILL.md` must stay at or below 780 estimated tokens. `SKILL.md` plus `agents/interface.yaml` must stay below 950 estimated tokens. Version metadata uses `updated_at: 2026-08-12` and `review_due: 2026-11-10`.

## Deferred work

Embedding retrieval and a cross-encoder route challenger are scheduled for Phase 2. Phase 1 uses deterministic semantic routing and frozen lexical/intent evidence.

Real DeepSeek runs and the three completed reviewer packets remain external prerequisites when `DEEPSEEK_API_KEY` or reviewer decisions are unavailable. Infrastructure can ship with `quality_promotion.status = pending`.
