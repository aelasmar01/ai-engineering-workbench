# Troubleshooting

## `uv` is missing

Install `uv` from the Astral documentation, then run `make setup` again.

## Node.js is too old

Use Node.js 22 or newer for the dashboard toolchain.

## `make check` fails in the dashboard

Run:

```bash
cd apps/dashboard
npm install
npm run typecheck
npm test
```

## `workbench doctor` reports missing optional tools

Docker, Codex CLI, and Claude Code are optional during Milestone 0. Later
milestones will require the selected tool only when a workflow uses it.

## SQLite database creation

Milestone 1 initializes SQLite tables through application code. If a database
file cannot be created, check that the parent directory exists or is writable by
the current user.
