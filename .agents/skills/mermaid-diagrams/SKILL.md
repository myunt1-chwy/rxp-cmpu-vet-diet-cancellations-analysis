---
name: mermaid-diagrams
description: Create, edit, and render Mermaid diagrams using the minlag/mermaid-cli Docker image. Use for Mermaid diagram sources and exported PNG, SVG, or PDF diagrams.
---

# Mermaid diagrams

Create or edit Mermaid source, then render it with the bundled helper. Run from
the repository root using `.venv/bin/python`; use `make setup` if needed.

Save new `.mmd` sources and rendered diagrams under `outputs/diagrams/`, using
matching descriptive basenames. Retain the source for future edits. Default to
PNG with a transparent background; use SVG or PDF when requested.

```sh
.venv/bin/python .agents/skills/mermaid-diagrams/scripts/render.py outputs/diagrams/workflow.mmd
.venv/bin/python .agents/skills/mermaid-diagrams/scripts/render.py outputs/diagrams/workflow.mmd -o outputs/diagrams/workflow.svg
```

The helper checks for Docker and an accessible daemon, mounts the source
directory read-only, and renders with `minlag/mermaid-cli:latest`. Docker can
download the image if absent. Do not install Docker or start its daemon
automatically: report the prerequisite error and stop. Surface image-pull and
rendering errors; correct invalid Mermaid source before retrying.

Inspect the generated PNG for readable labels, clipping, and layout before
delivery. For SVG/PDF requests, render a companion PNG for visual inspection.
Return links to the requested diagram and its `.mmd` source. Generated output
remains ignored by Git.

The helper accepts `INPUT [-o OUTPUT]`. Without `-o`, it writes
`outputs/diagrams/<input-stem>.png`. Explicit outputs must end in `.png`, `.svg`,
or `.pdf`. Successful renders replace the destination; failed renders preserve
an existing destination. All formats use Mermaid's transparent-background flag.

Reference: [Mermaid CLI Docker usage](https://github.com/mermaid-js/mermaid-cli#use-dockerpodman).
