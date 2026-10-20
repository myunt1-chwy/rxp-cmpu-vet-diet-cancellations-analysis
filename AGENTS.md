## Agent Instructions
- Keep changes small, boring, and reversible.
- Prefer existing package patterns over new abstractions
- If something is not clear
## Development Loop
- TODO.org contains the tasks that need to get done.
- Once a task is done, stop so that the user can check the work.
- Read before editing. Use rg/sed for fast context and avoid broad rewrites.
- Run make setup when dependencies or hooks are missing. Do not use global Python tools for repo commands; the project sandbox is .venv.
- Keep generated output out of Git. dist/, build/, caches, .sandbox/, .uv/, .venv, and .env are ignored.
## Commits And Branches
- Work on short-lived feature branches, not trunk.
- Use Conventional Commits: feat: for minor, fix:/perf: for patch or hotfix, and ! or BREAKING CHANGE: for major.
- After a task is done ask for approval to commit and make a commit.
## Repo Structure
- Any plan accepted by the user should be in the todo.org file as an emacs todo item.
- Log what is done in log.org after the user accepts the changes and code is committed.
- Any downloaded data should be put under the data directory.
- Any plots should be under the outputs/charts directory.
- Export data used to markdown tables for further analysis in outputs/tables/
- Any diagrams should be under the outputs/diagrams directory.
- Any tables should be in markdown and saved under outputs/tables directory
- Any PDF reports should be under   outputs/reports/pdf
- Any Word reports should be under  outputs/reports/docs
- Any markdown reports should be under outputs/reports/md
- Any code under src/ignore should be ignored from consideration. It
  can be committed but that is a code playground and the code may not
  be always correct
- HOWTO.md should contain how to run the make targets.
## Preferences
- For charts, use Altair in Python and export PNGs with transparent backgrounds by default.
- For diagrams use mermaid and use transparent backgrounds and export PNG by default.
- Python packages should be managed by uv
