# Semantic Operators Roadmap

Sigil now has two operator families:

```text
,    propose one concrete command or patch action
,,   execute/apply one typed proposal
,,,  durable plan stepper, one confirmed boxed step at a time

?    ask/inspect through the read/web route
??   follow up through the same read/web route
???  exhaustive read-only answer through the same route
```

The previous `^` repair surface is intentionally gone. Repair is context, not a
separate operator family: comma proposals can read the last failure, stdin, cwd,
and readable file targets, then choose `kind=command` or `kind=patch`.

## Current Stable State

Implemented:

- `src/sigil/cli.py` owns the shell-agnostic CLI boundary.
- `src/sigil/operators.py` parses `?` and `,` glyphs and runs typed comma
  proposals.
- `src/sigil/question.py` owns the Pi-backed read/web question path.
- `src/sigil/plans.py` owns the durable `,,,` plan stepper.
- `src/sigil/failure.py` still records last-failed-command context for comma
  proposals.
- `src/sigil/security.py` owns the trust lattice.
- `src/sigil/state.py` and `src/sigil/session.py` provide durable event and
  session state.
- `shell/zsh/sigil.zsh` and `shell/bash/sigil.bash` expose only comma and
  question glyphs.

## Operator Contracts

Question operators are read-only:

```text
?    fresh read/web answer
??   continuation with same-session transcript
???  exhaustive read/web answer
```

Comma operators are proposal/action routes:

```text
,    structured JSON: {kind, body, explanation}
,,   structured JSON: {kind, body}; execute commands, preview+confirm patches
,,,  durable plan state; execute at most one confirmed step per invocation
```

Piped input is treated as intentional context only after confirmation. Non-piped
`,,` may execute a generated command immediately. Patch proposals are always
previewed and confirmed before file writes.

## Remaining Work

Near-term hardening:

- Keep prompt/schema wording aligned with the typed proposal contract.
- Improve patch previews when a model returns a patch-like plan instead of a
  valid unified diff.
- Make `???` visibly distinct in the question prompt and event summary.
- Keep shell history behavior limited to command proposals from `,`.

Future autonomy:

- Expand `,,,` with bounded plan options such as skip/edit/quit and
  plan-scoped trust windows.
- Keep all autonomy durable in state files so work can resume across terminals.
- Preserve the rule that read/web output never becomes an executable proposal
  without fresh comma-route intent.
