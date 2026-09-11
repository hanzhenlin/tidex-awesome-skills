# Trusted Evidence Publication

`evidence-build` gives every Skill its own local run and release store. The store is rooted at the target Skill, so one Skill cannot reuse another Skill's run id, lock, artifacts, or release pointer.

## Build and publish

```bash
python3 scripts/yao.py evidence-build <skill_dir>
python3 scripts/yao.py evidence-build <skill_dir> --run-id <id> --publish
python3 scripts/yao.py evidence-build <skill_dir> --recover
```

The default command is a dry run. It copies current report artifacts into `.yao/runs/<run-id>/artifacts`, writes a run manifest, and creates a SHA-256 artifact index. Publishing requires a clean Git worktree. A successful publish creates `.yao/releases/<run-id>`, refreshes canonical report mirrors, writes `reports/artifact-index.json`, and updates `reports/.current-run.json` last.

Release bundle directories are immutable. Reusing a published run id is an error. Run ids accept letters, numbers, dots, underscores, and hyphens; absolute paths, parent traversal, symlink artifacts, and indexed paths outside the Skill root are rejected.

## Consumer contract

Official report consumers resolve report JSON through `scripts/evidence_resolver.py`. The resolver verifies the current artifact index and the selected artifact hash. A clean source checkout reads the immutable release bundle. A dirty authoring checkout reads its canonical candidate reports until they are committed and published. A packaged installation carries a portable pointer and report index, so canonical mirrors retain the same per-artifact hash check without `.yao/releases`.

## Crash recovery

Publishing writes `.yao/publish-transaction.json` and a canonical snapshot before mirrors change. A dry run reports `recovery-required` while this marker exists and does not modify canonical evidence. Run `evidence-build <skill_dir> --recover`, or use an explicitly requested `--publish`, to restore the previous bundle or the pre-publish snapshot. Recovery supports the first publication, removes the unreferenced incomplete release, and clears the transaction after the restored hashes pass.

Recovery failures are terminal. Preserve `.yao`, `reports/.current-run.json`, and `reports/artifact-index.json`, then inspect the error code and hashes before another publish attempt.
