from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ShellBindingTests(unittest.TestCase):
    def make_stub(self, tmp: Path) -> Path:
        stub = tmp / "sigil-stub"
        stub.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "$SIGIL_STUB_LOG"
                case "$*" in
                  "command --select hello") printf '%s\\n' "echo generated" ;;
                  "command --previous --select") printf '%s\\n' "echo previous" ;;
                  "fix") printf '%s\\n' "echo fix" ;;
                  "fix --previous") printf '%s\\n' "echo previous-fix" ;;
                  "question hello") printf '%s\\n' "answer" ;;
                  "question --follow-up hello") printf '%s\\n' "follow-up" ;;
                  "summary") printf '%s\\n' "summary" ;;
                  "summary now") printf '%s\\n' "summary now" ;;
                  record-failure*) printf '%s\\n' "recorded" ;;
                  *) printf '%s\\n' "unexpected:$*" >&2; exit 64 ;;
                esac
                """
            ),
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return stub

    def run_shell(
        self,
        shell: str,
        script: str,
        tmp: Path,
        stub: Path,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SIGIL_BIN"] = str(stub)
        env["SIGIL_STUB_LOG"] = str(tmp / "calls.log")
        env["SIGIL_SESSION_ID"] = "shell-test"
        return subprocess.run(
            [shell, "-c", script],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(
            result.returncode,
            0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def read_log(self, tmp: Path) -> list[str]:
        path = tmp / "calls.log"
        if not path.exists():
            return []
        return path.read_text(encoding="utf-8").splitlines()

    def test_bash_wrappers_call_current_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    sigil_command hello
                    sigil_previous_command
                    sigil_question hello
                    sigil_follow_up hello
                    sigil_fix
                    sigil_previous_fix
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(
                self.read_log(tmp),
                [
                    "command --select hello",
                    "command --previous --select",
                    "question hello",
                    "question --follow-up hello",
                    "fix",
                    "fix --previous",
                ],
            )
            self.assertIn("echo generated", result.stdout)
            self.assertIn("echo previous-fix", result.stdout)

    def test_bash_readline_dispatch_inserts_proposals_without_executing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    READLINE_LINE=", hello"
                    READLINE_POINT=${#READLINE_LINE}
                    __sigil_readline_dispatch >/tmp/sigil-shell-test.out
                    printf 'command_buffer=%s\\n' "$READLINE_LINE"

                    READLINE_LINE="^^"
                    READLINE_POINT=${#READLINE_LINE}
                    __sigil_readline_dispatch >/tmp/sigil-shell-test.out
                    printf 'fix_buffer=%s\\n' "$READLINE_LINE"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(
                self.read_log(tmp),
                ["command --select hello", "fix --previous"],
            )
            self.assertIn("command_buffer=echo generated", result.stdout)
            self.assertIn("fix_buffer=echo previous-fix", result.stdout)

    def test_bash_blocks_execute_and_promotion_routes_before_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    READLINE_LINE=",! rm -rf nope"
                    __sigil_readline_dispatch >/tmp/sigil-shell-test.out
                    printf 'bang_buffer=%s\\n' "$READLINE_LINE"

                    READLINE_LINE="@ promote"
                    __sigil_readline_dispatch >/tmp/sigil-shell-test.out
                    printf 'at_buffer=%s\\n' "$READLINE_LINE"

                    READLINE_LINE="?! run"
                    __sigil_readline_dispatch >/tmp/sigil-shell-test.out
                    printf 'question_bang_buffer=%s\\n' "$READLINE_LINE"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), [])
            self.assertIn("bang_buffer=", result.stdout)
            self.assertIn("at_buffer=", result.stdout)
            self.assertIn("question_bang_buffer=", result.stdout)

    def test_bash_question_routes_clear_the_prompt_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    READLINE_LINE="?? hello"
                    READLINE_POINT=${#READLINE_LINE}
                    __sigil_readline_dispatch
                    printf 'follow_up_buffer=%s\\n' "$READLINE_LINE"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), ["question --follow-up hello"])
            self.assertIn("follow_up_buffer=", result.stdout)

    def test_bash_summary_route_is_read_only_and_clears_the_prompt_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    READLINE_LINE="@. now"
                    READLINE_POINT=${#READLINE_LINE}
                    __sigil_readline_dispatch
                    printf 'summary_buffer=%s\\n' "$READLINE_LINE"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), ["summary now"])
            self.assertIn("summary_buffer=", result.stdout)

    def test_bash_records_failed_non_sigil_history_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    __sigil_history_line() { printf '%s\\n' "bad command"; }
                    false
                    __sigil_precmd
                    __sigil_history_line() { printf '%s\\n' ", should not record"; }
                    false
                    __sigil_precmd
                    :
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(
                self.read_log(tmp),
                [f"record-failure --status 1 --cwd {ROOT} bad command"],
            )

    def test_bash_does_not_record_failed_sigil_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    __sigil_history_line() { printf '%s\\n' "sigil bad"; }
                    false
                    __sigil_precmd
                    __sigil_history_line() { printf '%s\\n' "^"; }
                    false
                    __sigil_precmd
                    :
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), [])

    def test_bash_passes_failure_snippet_env_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "bash",
                textwrap.dedent(
                    """\
                    source shell/bash/sigil.bash
                    __sigil_history_line() { printf '%s\\n' "bad command"; }
                    export SIGIL_FAILURE_STDOUT="stdout line"
                    export SIGIL_FAILURE_STDERR="stderr line"
                    false
                    __sigil_precmd
                    :
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(
                self.read_log(tmp),
                [
                    f"record-failure --status 1 --cwd {ROOT} "
                    "--stdout-snippet stdout line "
                    "--stderr-snippet stderr line bad command"
                ],
            )

    @unittest.skipIf(shutil.which("zsh") is None, "zsh is not installed")
    def test_zsh_wrappers_call_current_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "zsh",
                textwrap.dedent(
                    """\
                    source shell/zsh/sigil.zsh
                    sigil_command hello
                    sigil_previous_command
                    sigil_question hello
                    sigil_follow_up hello
                    sigil_fix >/tmp/sigil-zsh-fix.out
                    sigil_previous_fix >/tmp/sigil-zsh-prev-fix.out
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(
                self.read_log(tmp),
                [
                    "command --select hello",
                    "command --previous --select",
                    "question hello",
                    "question --follow-up hello",
                    "fix",
                    "fix --previous",
                ],
            )

    @unittest.skipIf(shutil.which("zsh") is None, "zsh is not installed")
    def test_zsh_accept_line_inserts_fix_proposals_without_executing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "zsh",
                textwrap.dedent(
                    """\
                    function zle { :; }
                    source shell/zsh/sigil.zsh
                    BUFFER="^"
                    CURSOR=1
                    __sigil_accept_line
                    print -- "buffer=$BUFFER"
                    print -- "cursor=$CURSOR"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), ["fix"])
            self.assertIn("buffer=echo fix", result.stdout)
            self.assertIn("cursor=8", result.stdout)

    @unittest.skipIf(shutil.which("zsh") is None, "zsh is not installed")
    def test_zsh_blocks_execute_and_promotion_routes_before_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "zsh",
                textwrap.dedent(
                    """\
                    function zle { :; }
                    source shell/zsh/sigil.zsh
                    BUFFER=",! rm -rf nope"
                    __sigil_accept_line
                    print -- "bang_buffer=$BUFFER"
                    BUFFER="@ promote"
                    __sigil_accept_line
                    print -- "at_buffer=$BUFFER"
                    BUFFER="?! run"
                    __sigil_accept_line
                    print -- "question_bang_buffer=$BUFFER"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), [])
            self.assertIn("bang_buffer=,! rm -rf nope", result.stdout)
            self.assertIn("at_buffer=@ promote", result.stdout)
            self.assertIn("question_bang_buffer=?! run", result.stdout)

    @unittest.skipIf(shutil.which("zsh") is None, "zsh is not installed")
    def test_zsh_does_not_record_failed_sigil_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "zsh",
                textwrap.dedent(
                    """\
                    source shell/zsh/sigil.zsh
                    __sigil_preexec "sigil bad"
                    false
                    __sigil_precmd
                    __sigil_preexec "^"
                    false
                    __sigil_precmd
                    :
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), [])

    @unittest.skipIf(shutil.which("zsh") is None, "zsh is not installed")
    def test_zsh_summary_route_is_read_only_and_clears_the_prompt_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            stub = self.make_stub(tmp)
            result = self.run_shell(
                "zsh",
                textwrap.dedent(
                    """\
                    function zle { :; }
                    source shell/zsh/sigil.zsh
                    BUFFER="@. now"
                    __sigil_accept_line
                    print -- "summary_buffer=$BUFFER"
                    """
                ),
                tmp,
                stub,
            )
            self.assert_success(result)
            self.assertEqual(self.read_log(tmp), ["summary now"])
            self.assertIn("summary_buffer=", result.stdout)


if __name__ == "__main__":
    unittest.main()
