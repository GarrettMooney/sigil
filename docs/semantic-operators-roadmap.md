# Semantic Operators Roadmap

This records the current v1 direction for Sigil's shell glyphs. The public
glyph surface keeps comma routes plus explicit `+`; question glyphs are removed.

## Target Grammar

```text
,    answer from read-only context
,,   one agent step, confirm effects
,,,  one agent step, auto-approve routine effects
```

More punctuation grants more authority on the comma axis. It should not secretly
change the unit of work beyond the documented route.

## Removed Behavior

The migration intentionally removes these meanings:

- `??` no longer means follow up on the previous answer.
- `???` no longer means exhaustive question.
- `?` and `??` are no longer Sigil glyphs.
- `,` no longer proposes a command.
- `,,` no longer means generate and execute one shell command.
- `,,,` no longer means the only agentic/editing route.

If follow-up remains useful, keep it as explicit CLI behavior such as
`sigil ask --follow-up`, not as a glyph. If exhaustive answers remain useful,
make them prompt text or a long-form flag, not `???`.

## Read Routes

`,` answers with local read-only context. It may use shell/session context and
the read-only inspection tools (`read`, `grep`, `ls`), but it has no Bash
execution path. If an answer recommends a command, it is plain answer text.

`sigil ask` remains the explicit named read-only CLI route. `sigil command`
remains the explicit named command-proposal CLI route.

## Comma Routes

`,,` runs one agent step after showing the step and asking before effects.

`,,,` runs one agent step without routine per-step confirmation. The shell
remains the review boundary: Bash tool execution is blocked and staged as a
command for explicit review rather than run inline.

Implementation notes:

- Refactor the existing act stepper so it can run with `confirm_step=True` for
  `,,` and `confirm_step=False` for `,,,`.
- Make the step runner accept the originating glyph so tool traces match the
  route.
- Preserve the "one step, then return control" invariant for both `,,` and
  `,,,`.

## Parser Rules

Supported operators:

```text
,   depth 1..3
```

Invalid:

```text
?
??
mixed glyph tokens such as ,?
```

## TODO

- [x] Update operator parsing to support per-glyph max depths.
- [x] Reject question glyphs with clear errors.
- [x] Refactor `ask()` to use explicit source authorization instead of
      `follow_up`.
- [x] Route `,` through read-only tools.
- [x] Remove `?` and `??` glyph routes.
- [x] Update question trust fields to use named/glyph routes.
- [x] Remove glyph-level follow-up and exhaustive-question behavior.
- [x] Keep or remove `sigil ask --follow-up` as an explicit CLI decision.
- [x] Refactor the act stepper to accept `confirm_step` and `glyph`.
- [x] Route `,,` to one confirmed agent step.
- [x] Route `,,,` to one auto-approved agent step within policy.
- [x] Ensure `,,,` still stops at explicit policy boundaries.
- [x] Extract shared Zeta agent-step execution for comma routes.
- [x] Update zsh bindings for `,`, `,,`, `,,,`, and `+`.
- [x] Update Bash bindings for `,`, `,,`, `,,,`, and `+`.
- [x] Remove shell bindings for `?`, `??`, and `???`.
- [x] Update README glyph reference and examples.
- [x] Update CLI docs and trust model docs.
- [x] Rewrite tests for question routing and alpha trust records.
- [x] Rewrite tests for comma routing.
- [x] Add tests that question glyphs fail.
- [x] Run the full test suite.
