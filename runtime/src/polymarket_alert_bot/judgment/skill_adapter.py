from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
from collections.abc import Callable
from typing import Any

from polymarket_alert_bot.judgment.contract import runtime_request_envelope
from polymarket_alert_bot.judgment.result_parser import (
    ParsedJudgment,
    ParseError,
    parse_judgment_result,
)

SkillRunner = Callable[[dict[str, Any], int], dict[str, Any] | str]
ExternalCommandRunner = Callable[[list[str], str, int], dict[str, Any] | str]
DEFAULT_EXTERNAL_RUNNER_ENV = "POLYMARKET_ALERT_BOT_JUDGMENT_RUNNER_CMD"


class SkillAdapter:
    """Adapter around the runtime judgment contract."""

    def __init__(
        self,
        *,
        runner: SkillRunner | None = None,
        timeout_seconds: int = 600,
        external_command: list[str] | str | None = None,
        external_runner: ExternalCommandRunner | None = None,
    ) -> None:
        self._runner = runner
        self.timeout_seconds = timeout_seconds
        self._external_command = self._normalize_command(external_command)
        self._external_runner = external_runner or self._run_external_command

    def build_payload(self, context: dict[str, Any]) -> dict[str, Any]:
        return runtime_request_envelope(context)

    def judge(self, context: dict[str, Any]) -> ParsedJudgment:
        payload = self.build_payload(context)
        raw: dict[str, Any] | str
        try:
            if self._runner is not None:
                raw = self._runner(payload, self.timeout_seconds)
            elif self._external_command:
                raw = self._external_runner(
                    self._external_command,
                    json.dumps(payload, ensure_ascii=False),
                    self.timeout_seconds,
                )
            else:
                return ParsedJudgment.degraded("runner_not_configured")
        except TimeoutError:
            return ParsedJudgment.degraded("skill_timeout")
        except Exception:
            return ParsedJudgment.degraded("runner_execution_failed")

        try:
            return parse_judgment_result(raw)
        except ParseError:
            return ParsedJudgment.degraded("malformed_skill_output")

    @staticmethod
    def _normalize_command(command: list[str] | str | None) -> list[str]:
        if command is None:
            env_command = os.environ.get(DEFAULT_EXTERNAL_RUNNER_ENV, "").strip()
            if not env_command:
                return []
            return SkillAdapter._split_command_text(env_command)
        if isinstance(command, str):
            text = command.strip()
            return SkillAdapter._split_command_text(text) if text else []
        return SkillAdapter._coalesce_inline_script(
            [str(part).strip() for part in command if str(part).strip()]
        )

    @staticmethod
    def _coalesce_inline_script(parts: list[str]) -> list[str]:
        if "-c" not in parts:
            return parts
        script_index = parts.index("-c")
        if script_index == len(parts) - 1:
            return parts
        # Tests and operator config often provide `python -c <script>` as a plain
        # joined string rather than shell-quoted argv. Re-join the inline script so
        # subprocess receives a valid `-c` payload.
        return [*parts[: script_index + 1], " ".join(parts[script_index + 1 :])]

    @staticmethod
    def _split_command_text(text: str) -> list[str]:
        marker = " -c "
        if marker not in text:
            return SkillAdapter._coalesce_inline_script(shlex.split(text))
        prefix, inline_script = text.split(marker, maxsplit=1)
        prefix_parts = shlex.split(prefix)
        if not prefix_parts:
            return []
        return [*prefix_parts, "-c", inline_script]

    @staticmethod
    def _run_external_command(command: list[str], payload_json: str, timeout_seconds: int) -> str:
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            stdout_text, stderr_text = process.communicate(
                input=payload_json,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                finally:
                    try:
                        process.communicate(timeout=1)
                    except Exception:
                        pass
            raise TimeoutError("external skill runner timed out") from exc

        if process is None:
            raise RuntimeError("external runner failed to start")

        if process.returncode != 0:
            stderr_text = (stderr_text or "").strip()
            raise RuntimeError(
                f"external runner exited with code {process.returncode}: {stderr_text}"
            )

        stdout_text = (stdout_text or "").strip()
        if not stdout_text:
            raise RuntimeError("external runner returned empty stdout")
        return stdout_text
