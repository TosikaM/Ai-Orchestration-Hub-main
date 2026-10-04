# Command: git

Used by the `git-workflow` skill.

## Steps
1. Load the parent `SKILL.md`.
2. Confirm `verification-loop` passed. If it did not, stop and say which phase failed.
3. `python scripts/git-flow.py status` — check the branch and what is staged.
4. Branch if on the default branch. Commit. Push and open the PR only at autonomy 4.
5. Report the branch, the commit sha, and the PR URL.

## Outputs
- A branch, a commit, and a pull request — or, below level 4, the branch contents and
  PR body as artifacts for a human to push.

## Rules
- Never commit to the default branch; the script refuses.
- Never force-push. There is no code path for it and the destructive gate forbids it.
- There is no merge step, at any autonomy level.
