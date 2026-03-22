# Tool Docs Skill

Use this when writing or revising docs for a CLI, local service, operator script, or small developer tool.

The goal is simple: a reader should be able to install the tool, run it, verify it, and recover from failure without reading the source.

## What Good Tool Docs Must Do

Tool docs should answer these quickly:

1. What is this tool for?
2. How do I install it?
3. What command do I run first?
4. How do I know it is working?
5. How do I stop it?
6. Where do I look when it fails?

If those answers are not obvious in under a minute, the docs are too hard to use.

## Default Structure

Use this order unless there is a strong reason not to:

1. Short summary
2. Out-of-the-box capabilities
3. Start here / quick start
4. Outputs and interfaces
5. Foreground vs background operation
6. Recovery and debugging
7. API / integration details
8. Configuration reference
9. Command reference

Put the happy path before the reference material.

## Writing Rules

### Start With The Job

Lead with:

- what problem the tool solves
- who it is for
- what it produces
- the first command most users should run

Do not open with flags, internals, or edge cases.

### Be Concrete

Prefer real commands and real paths:

- `uv run np serve`
- `open http://127.0.0.1:8976/`
- `_data/current_song.txt`

Avoid vague language when a short example would be clearer.

### Separate Interfaces Clearly

If a tool exposes more than one interface, name them explicitly:

- human-facing viewer
- machine-facing JSON endpoint
- flat-file outputs
- logs

Do not assume the reader will infer the difference.

### Document Side Effects

Call out what changes system state:

- installs a LaunchAgent
- leaves a background service running
- writes files under `_data/`
- updates OBS over websocket

Users should not discover side effects by accident.

### Tell The Truth

If something is beta, flaky, platform-specific, or incomplete, say that directly.

Examples:

- auto-detection works but is still being validated
- foreground mode is the best debugging path
- a command exists, but richer diagnostics do not yet

Honest docs build trust faster than polished fiction.

### Keep Reference Tight

Command docs should be easy to scan:

- one line for what the command does
- one short note for unusual behavior
- one example when needed

Config docs should explain impact, not just variable names.

## Required Workflow

When revising tool docs, use this process:

1. Read the actual CLI help and config template.
2. Check the docs against current behavior.
3. Rewrite the start path so first use is obvious.
4. Make interfaces and side effects explicit.
5. Add recovery steps for common failures.
6. Run a devil’s-advocate pass.
7. Polish using that feedback.

Do not stop after “technically correct.” Aim for “hard to misuse.”

## Devil's-Advocate Pass

Before calling the docs done, read them as if you are:

- impatient
- skeptical
- distracted
- unfamiliar with the code

Ask:

- Do I know what to run first?
- Do I know what success looks like?
- Do I know which URL is for humans and which is for machines?
- Do I know whether this command leaves something running?
- Do I know what to do if the default port is already in use?
- Do I know how to stop the service?
- Do I know where logs are or how to tail them?
- Are any sections duplicated, contradictory, or overly cute?

Then revise the docs using that pass as input, not as a separate report.

## Good Defaults

Assume the reader wants the simplest path:

- local loopback host
- sensible polling interval
- file-based OBS integration first

Show advanced options only after the default setup is clear.

## Recovery Is Part Of The Product

Good tool docs explain how to get unstuck:

- how to see logs
- how to stop background services
- how to rerun in the foreground
- how to verify current state

The recovery path is part of the product, not an afterthought.
