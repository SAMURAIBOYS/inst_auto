## Summary
- What changed?
- Why was it needed?

## Codex review handoff
- [ ] Request Codex review on this PR
- [ ] Confirm the required GitHub Actions checks are green
- [ ] Enable GitHub auto-merge only after required checks and reviews pass

## Required checks
- `pipeline-smoke (ubuntu-latest)`
- `pipeline-smoke (windows-latest)`
- `regression-guards`

## Notes
- If CI fails, do not enable auto-merge.
- If branch protection or required checks changed, update the README operations section.

## Merge strategy
- [ ] Use **Squash merge** by default
- [ ] Use **Rebase merge** only when commit history should be preserved
