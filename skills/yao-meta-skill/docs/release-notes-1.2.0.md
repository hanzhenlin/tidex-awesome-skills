# Yao Meta Skill 1.2.0 Release Candidate

Version 1.2.0 adds the first trusted generation core for governed skill delivery. The candidate is ready for engineering review and beta testing. Quality promotion remains pending until the formal DeepSeek matrix and three-reviewer blind evaluation are complete.

## What changed

1. **Trusted evidence publishing.** Each build runs in an isolated workspace and can publish an immutable evidence bundle through transactional recovery, pointer-last updates, portable indexes, and path-boundary checks.
2. **Canonical Skill IR resolution.** Manifests can declare `skill_ir_source`, and compilers, packaging, registry, conformance, Overview, and Review Studio now resolve the same validated IR instead of scanning wildcard examples.
3. **Governed output evaluation.** The committed provider matrix fixes DeepSeek V4 Flash and V4 Pro, 40 planned calls, a 250,000-token budget, isolated raw outputs, 20 randomized A/B pairs, three controlled reviewer packets, and multi-reviewer adjudication.
4. **Frozen trigger and context gates.** A locked 30-case holdout now guards precision, recall, hard negatives, the existing 66-case suite, the 780-token skill body limit, and the 950-token initial-load limit.
5. **Deterministic packaging and install proof.** Archive verification now compares the actual ZIP digest across package and registry evidence, excludes self-referential checksum consumers, and installs the exact attested bytes through a portable report index.
6. **Clear release boundaries.** Benchmark, Skill OS audit, Review Studio, and world-class evidence reports now separate legacy evidence, Phase 1 completion, beta readiness, quality promotion, and public claim readiness.

## Compatibility and migration

- The declared version bump is minor, with no removed targets or reported breaking changes.
- Agent Skills-compatible, VS Code, OpenAI, Claude, and generic targets remain supported in 1.2.0.
- Governed packages should add `skill_ir_source` and adopt the evidence pointer, recovery, provider, and review contracts in [Migration to 1.2.0](migration-1.2.0.md).

## Verified candidate state

- Package version: `1.2.0`
- Cross-platform conformance: `5 / 5`
- Full CI: `83 / 83`
- Frozen trigger holdout: precision `1.000`, recall `0.917`, hard-negative false positives `0`
- Context budgets: `764` skill-body tokens and `947` initial-load tokens
- Evidence consistency: `41 / 41`, with zero warnings and zero failures
- Package verification: zero nested skill entrypoints, zero warnings, and zero failures

The engineering release lock is ready. The formal provider matrix remains at `0 / 40`, the human review remains at `0 / 3`, and quality promotion and world-class claims remain pending.

## Review artifacts

- [Phase 1 trusted generation visual report](../reports/phase1-trusted-generation-visual-report-v2.html)
- [Phase 1 repair checklist](../reports/phase1-review-repair-checklist.md)
- [Package verification](../reports/package_verification.md)
- [Evidence consistency](../reports/evidence_consistency.md)
- [Provider output status](../reports/provider_output_evaluation.json)
