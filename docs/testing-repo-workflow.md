# Testing Repo Workflow

Use `https://github.com/aelasmar01/testing-repo.git` as a safe manual workflow
target for AI Engineering Workbench.

## Repository setup

Clone the fixture repository outside this workbench repository:

```bash
cd /Users/aliel-asmar/Desktop
git clone https://github.com/aelasmar01/testing-repo.git
```

The repository contains a minimal Python module and `harness.yaml` with `test`
and `lint` checks. The checks avoid writing bytecode files so `workbench diff`
stays clean after validation.

## Isolated workbench data

Use a dedicated data directory when testing:

```bash
export WORKBENCH_DATA_DIR=/Users/aliel-asmar/Desktop/workbench-testing-data
```

This keeps test runs separate from your normal workbench database, evidence, and
worktrees.

## Register and start

From the workbench repository:

```bash
cd /Users/aliel-asmar/Desktop/ai-engineering-workbench
uv run workbench project add /Users/aliel-asmar/Desktop/testing-repo
uv run workbench task add examples/testing-repo-task.yaml
uv run workbench task start TEST-001
```

The task worktree is created at:

```text
/Users/aliel-asmar/Desktop/workbench-testing-data/worktrees/testing-repo/TEST-001
```

## Make a test change

Edit the generated worktree, not the base repository:

```bash
$EDITOR /Users/aliel-asmar/Desktop/workbench-testing-data/worktrees/testing-repo/TEST-001/src/app.py
```

Keep the greeting starting with `hello` so the fixture validation remains green.

## Validate and review

```bash
uv run workbench check TEST-001
uv run workbench evidence TEST-001
uv run workbench diff TEST-001
uv run workbench acceptance verify TEST-001 \
  --criterion "Greeting behavior is updated" \
  --evidence-type validation \
  --evidence-reference "test and lint checks passed"
uv run workbench pr prepare TEST-001
```

At this point, `workbench pr status TEST-001` should show a prepared PR record.

## Optional live PR

Only run this when you intentionally want to push a branch and open a GitHub PR
against the testing repository:

```bash
uv run workbench pr create TEST-001 --yes
```

The workbench does not merge the PR.

## Reset the manual test

Remove the isolated data directory and delete the test branch from the base
repository if you want a clean rerun:

```bash
rm -rf /Users/aliel-asmar/Desktop/workbench-testing-data
git -C /Users/aliel-asmar/Desktop/testing-repo branch -D feat/TEST-001-update-greeting-message
```

If you opened a live PR, close it on GitHub before deleting remote branches.
