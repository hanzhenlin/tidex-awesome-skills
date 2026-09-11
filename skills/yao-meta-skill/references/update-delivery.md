# Update Delivery

Use this reference when an activation check reports a newer stable Yao Meta Skill version or the user asks to update the installed Skill.

## Release Signal

- `VERSION` on the official default branch is the primary stable release signal.
- The official `manifest.json` version is the fallback when `VERSION` is unavailable or invalid.
- Only a higher `MAJOR.MINOR.PATCH` value qualifies. Ordinary commits and prerelease labels do not prompt an update.
- Activation checks use a 24-hour user-cache entry and record the version already shown to the user.

## User Experience

When `notify_user` is true, show this message and continue the current task:

```text
发现 Yao Meta Skill <local> → <remote>，回复“更新”即可升级；当前任务可以继续。
```

The reply “更新” authorizes one named update attempt in the current task. Run:

```bash
python3 <skill-base-dir>/scripts/yao.py self-update --self --yes
```

After success, tell the user to restart Codex or the active AI client.

## Managed Channels

- Agent Skills CLI: the active `~/.agents/skills/yao-meta-skill` copy must have an official `yaojingang/yao-meta-skill` entry in `~/.agents/.skill-lock.json`. The updater runs `npx -y skills update yao-meta-skill -g -y`.
- Codex plugin: the installed plugin manifest must point to the official GitHub repository. The updater refreshes that plugin's marketplace snapshot.
- Multiple managed channels require manual cleanup or an explicit channel choice outside this command. The updater does not guess.
- Development checkouts, direct copies, missing install records, non-official sources, and dirty Git worktrees remain read-only.

## Safety And Recovery

- `self-update` is a plan-only command until `--yes` is present.
- Update commands use argument arrays without shell interpolation.
- Custom update URLs may be used for diagnostic checks only; self-update always uses the official source.
- A failed installer command reports the execute stage and bounded stderr/stdout excerpts.
- A successful installer command must be followed by version and channel verification. A verification mismatch is reported as a partial update and never presented as success.
- Re-running after a successful update is idempotent because equal versions produce `current`.

## Optional Background Reminder

A portable Skill can check only while an AI task is active. Users who want reminders while the Skill is idle can create a user-owned Codex recurring automation that runs the read-only `check-update --notice` command. The Skill package does not create or mutate automations.
