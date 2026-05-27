# Sigil CLI contract

Sigil's human-readable output is allowed to evolve. Machine-readable output is
available through explicit `--json` flags and should remain stable across
compatible releases.

Status, progress, warnings, and errors are written to stderr. JSON output is
written to stdout.

## Top-level examples

```sh
sigil command --select "find large files"
sigil ask --json "what changed in this repo?"
git diff | sigil ask "review risky changes"
printf '%s\n' src/sigil/cli.py | sigil op "," "preview a cleanup"
sigil op --dry-run ",," "clean build outputs"
sigil patch check
sigil patch apply --yes
sigil install zsh
sigil install zsh --no-glyphs
sigil doctor
sigil events lineage
sigil session show --json
```

## `sigil op --json`

Parses a glyph invocation without running the model. This is the stable
machine-readable introspection path for shell bindings and tests.

```json
{
  "glyph": "??",
  "base": "?",
  "depth": 2,
  "name": "inspect",
  "prompt": "review risky changes",
  "stdin": "diff --git a/file b/file\n",
  "mode": "pipeline"
}
```

Stable fields:

- `glyph`
- `base`: the operator family, currently `?` or `,`.
- `depth`: repeated-glyph count.
- `name`: semantic operator name.
- `prompt`: user prompt text after the glyph.
- `stdin`: captured input stream.
- `mode`: `pipeline` or `interactive`.

Without `--json`, `sigil op` runs the operator. `?` answers through the
web-authorized read route, `??` continues that route, `???` asks for an
exhaustive read-only answer, `,` recommends one typed command or patch proposal,
`,,` executes a generated command or previews and confirms a generated patch, and
`,,,` runs the durable plan stepper. Operator output is written to stdout; status
and errors go to stderr.

## Verb Pipeline Commands

`sigil command` and `sigil ask` are the public verb layer. When stdin is piped
into `command` or `ask`, the verb uses the stream operator runtime and grounds
the result in stdin. Piped question routes ask before sending stdin to Pi:

```sh
cat notes.md | sigil command "draft a release command"
git diff | sigil ask "review risky changes"
```

## `sigil ask --json`

Runs the Pi question pipeline and emits one JSON object instead of rendering
Markdown through `glow`. `sigil ask --follow-up --json` uses the same shape with
`follow_up: true`.

Stable fields:

- `ok`: `true` when the stream renderer completed successfully.
- `type`: currently always `"answer"`.
- `question`: user-visible question text.
- `prompt`: expanded prompt sent to Pi. For follow-ups, this includes context.
- `follow_up`: whether this was invoked through `sigil ask --follow-up --json`.
- `answer`: concatenated assistant text.
- `answer_event_id`: event id for the stored answer, or `null` if no answer text
  was emitted.
- `tools`: ordered Pi tool trace events.
- `malformed_events`: count of malformed Pi JSON event lines ignored.

## `sigil plan`

`sigil plan show`, `sigil plan resume`, and `sigil plan abort` inspect and
control the durable plan used by `,,,`. A plan resume executes at most one
confirmed boxed step, then returns to the shell.
- `security`: trust metadata applied to the answer and tool trace.

Double comma is the comma execution route:

```sh
sigil op ",," "find all Python files"
git diff | sigil op ",," "run the relevant formatter"
sigil op --dry-run ",," "find all Python files"
```

Current comma behavior:

- `,` asks for structured JSON with `kind`, `body`, and `explanation`, prints
  the body followed by the explanation, and the shell binding adds command
  proposals to shell history.
- non-piped `,,` asks the model for one typed proposal. Command proposals execute
  through the user's shell, emit command stdout, and forward command
  stderr/status. Patch proposals are stored, previewed, and applied only after
  confirmation.
- piped comma routes preview stdin and ask before using it; piped `,,` also
  shows generated commands and asks before execution.
- `--dry-run` prints the generated command or patch without executing/applying it.

The policy classifier records broad action classes such as `execute`,
`file_write`, `network`, `delete`, and `privileged` in the event log.

## `sigil patch`

Double comma patch proposals store unified diffs as the current session's patch
preview before asking to apply them. The explicit patch commands remain available
for reviewing or applying the latest stored preview later.

```sh
sigil patch show
sigil patch check
sigil patch apply --yes
```

`show` prints the stored diff. `check` runs `git apply --check` in the working
directory where the preview was created. `apply` requires `--yes` and then runs
`git apply`; without `--yes`, it exits with status `2` and does not modify
files.

The JSON form is available for every subcommand:

```sh
sigil patch show --json
sigil patch check --json
sigil patch apply --yes --json
```

`check` and `apply` record audit events with the patch event id, command,
status, cwd, and bounded stdout/stderr snippets.

## `sigil events --json`

Shows recent records from the read-only global event log.

```sh
sigil events
sigil events --limit 50
sigil events --json
sigil events --json --raw
sigil events list --json
```

Without `--json`, each event is printed as a width-aligned activity feed:

```text
time  id  action  trust  session  summary
```

`action` combines the route glyph and lifecycle event, for example `? inspect`,
`,, executed`, or `,, patch check`. The JSON form returns the same summary
fields plus the full event id, cwd, raw type, raw glyph, and a ready-to-run
`lineage` command. Use `--raw --json` when you need exact stored event payloads.
The explicit `list` subcommand is an alias for the default `sigil events` view.

## `sigil events lineage --json`

Inspects the read-only global event log and returns the selected event plus the
transitive input events it inherited from.

```sh
sigil events lineage
sigil events lineage <event-id>
sigil events lineage <event-id> --json
```

When no event id is provided, Sigil uses the latest event from the current
session, falling back to the latest global event. The JSON form returns:

- `event_id`: selected event id.
- `nodes`: ordered lineage nodes starting with the selected event.
- `nodes[].depth`: distance from the selected event.
- `nodes[].event`: normalized event payload with trust metadata.
- `missing_inputs`: input ids referenced by events but absent from the log.

## `sigil session --json`

`session` has four JSON forms:

```sh
sigil session show --json
sigil session path --json
sigil session list --json
sigil session clear --json
```

`show` returns the current session id, path, and parsed continuity files.
`path` returns the global state path, current session path, session id, and
global event log path. `list` returns known session directories, files present in
each, and the latest event cwd/type/time when available. `clear` returns the
session files removed.

A session is one terminal shell by default. Installed Bash and zsh bindings set
`SIGIL_SESSION_ID` once when the shell starts, so separate terminal windows or
tabs keep separate `last-*` continuity. Override `SIGIL_SESSION_ID` or
`SIGIL_SESSION_DIR` only when you intentionally want to share or pin a session.

## Optional Glyph Aliases

Glyphs are a shell alias layer over the CLI runtime. Installed shell bindings
enable them by default; use `sigil install <shell> --no-glyphs` for a long-form
only setup.

```text
,   -> sigil op ","
,,  -> sigil op ",,"
,,, -> sigil op ",,,"   durable plan stepper
?   -> sigil op "?"
??  -> sigil op "??"
??? -> sigil op "???"
```

## Hidden plumbing commands

These commands are intentionally not shown in top-level help and are not stable
user-facing API:

- `sigil render-pi-stream`
- `sigil record-failure`
- `sigil op`

They exist so shell bindings can keep a small, explicit boundary with the Python
runtime.

`record-failure` accepts optional `--stdout-snippet` and `--stderr-snippet`
fields. The passive shell hooks cannot safely capture arbitrary command output
by themselves, but callers that already have bounded snippets can pass them
through this stable hidden boundary.

## `sigil install`

Installs or updates a shell binding from the installed Sigil package and adds an
idempotent source block to the shell rc file.

```sh
sigil install zsh
sigil install bash
```

Useful options:

```sh
sigil install bash --install-dir ~/.sigil/shell/bash --rc ~/.bashrc
sigil install zsh --json
```

The JSON form reports:

- `shell`: installed shell binding.
- `binding_path`: binding file written by Sigil.
- `rc_path`: rc file inspected or updated.
- `source_path`: bundled binding source copied from.
- `wrote_rc`: whether Sigil appended a source block.
- `glyphs_enabled`: whether the rc snippet enables punctuation aliases.

## `sigil doctor`

Checks local install readiness:

```sh
sigil doctor
sigil doctor --shell bash
sigil doctor --json
```

Doctor checks:

- `sigil`, `glow`, and `pi` are on `PATH`.
- the local model endpoint is reachable from `QWEN_URL`, or the default local
  endpoint.
- `QWEN_MODEL` is set when the endpoint needs an explicit model name.
- Sigil's state directory is writable.
- the selected shell is supported.
- the selected shell binding is installed.
- the current environment looks like it inherited a loaded binding.

The JSON form returns an ordered list of checks with `name`, `status`, `detail`,
and optional `hint`. `doctor` exits nonzero when any check has `status: "fail"`;
warnings do not change the exit code.
