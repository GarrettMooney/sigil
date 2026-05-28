# Sigil Trust Model

Sigil records where an answer or action came from and what it was allowed to
do. This metadata is visible through `sigil events`, `sigil events lineage`,
and `sigil session show --json`.

## Trust Fields

User-facing event records can include:

```json
{
  "glyph": "?",
  "inputs": ["event-id"],
  "integrity": "web",
  "capability": "read",
  "taint": ["web"],
  "provisional": true
}
```

Fields:

- `glyph`: route that produced the record, such as `,`, `,,`, `,,,`, `?`, `??`,
  `@`, or `@@`.
- `inputs`: previous event ids used as context.
- `integrity`: origin label, ordered as `human > local_model > local_file > web
  > unknown`.
- `capability`: maximum effect class, ordered as `none < propose < read <
  write_boxed < exec_boxed`.
- `taint`: accumulated source labels, currently most often `model`, `web`, or
  `legacy`.
- `provisional`: whether the record should be treated as provisional context
  rather than stable authority.

## Route Mapping

```text
,    local model proposal
     integrity=local_model
     capability=propose
     taint=["model"]

,,   confirmed Pi agent step
     step decision event: capability=none
     step execution event: capability=exec_boxed
     taint=["model"]

,,,  auto-approved Pi agent step
     act creation events: capability=propose
     step execution events: capability=exec_boxed
     taint=["model"]

?    local read question
     integrity=local_model
     capability=read
     taint=["model"]
     provisional=true

??   read/web question
     capability=read
     taint includes "web"
     provisional=true

@    confirmed goal loop
     goal and step events: capability=exec_boxed
     taint=["model"]

@@   auto-approved goal loop
     goal and step events: capability=exec_boxed
     taint=["model"]
```

Question routes never expose Bash to Pi. Comma and goal agent steps may hand off
a proposed Bash command, but they do not execute it through Pi. In zsh the shell
binding inserts the handed-off command into the editable prompt buffer; Bash
stores it in history. Execution and file writes happen through Pi
edit/write tools, or through the user pressing Enter on an edited handoff
command.

## Practical Examples

List recent events:

```sh
sigil events
```

Example table:

```text
time      id        action       trust                   session   summary
12:00:01  e3b0c442  ? question   local_model/read        9aa2f6e1  what changed?
12:01:10  2f7d6a8c  , recommend  local_model/propose     9aa2f6e1  run the tests
12:01:18  b1c4a901  ,, step      local_model/exec_boxed  9aa2f6e1  run the tests
```

Inspect provenance:

```sh
sigil events lineage b1c4a901
```

JSON lineage includes the selected event, any input events, and missing input
ids if an event references records that are no longer present:

```json
{
  "event_id": "b1c4a901-...",
  "nodes": [
    {
      "id": "b1c4a901-...",
      "depth": 0,
      "event": {
        "type": "act_step_executed",
        "glyph": ",,",
        "integrity": "local_model",
        "capability": "exec_boxed",
        "taint": ["model"]
      }
    }
  ],
  "missing_inputs": []
}
```

## Legacy State

Older state records may not contain trust fields. When Sigil reads those
records, it treats them conservatively:

```text
integrity=unknown
capability=none
taint=["legacy"]
provisional=false
inputs=[]
```

That lets old records remain inspectable without treating them as trusted
current context.

## User Rules

- `,` recommends; it does not execute.
- `,,` executes at most one confirmed Pi agent step per invocation.
- `,,,` executes at most one auto-approved Pi agent step per invocation.
- `@` and `@@` run bounded goal loops with budgets and checkpoints.
- `?` is a local read question route with no Bash tool.
- `??` is a read/web question route with no Bash tool.
