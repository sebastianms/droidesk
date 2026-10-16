"""Tests for the DEV-LOG hook. All fixtures are synthetic."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

sys.dont_write_bytecode = True
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import devlog

HOOK_SCRIPT = HOOKS_DIR / "devlog.py"
SESSION_ID = "2680e3d9-8a04-4c9b-80ba-f0d66c3200d8"
MODEL = "claude-opus-5-5"
SUBAGENT_MODEL = "claude-sonnet-5-5"
TIME_OF_DAY = re.compile(r"\d{1,2}:\d{2}")
CALENDAR_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def make_secret(prefix: str, length: int) -> str:
    """Build a fake secret at runtime so this file never holds a scannable literal."""
    return prefix + ("aB3dE5gH7j" * length)[:length]


def usage(input_tokens: int, cache_read: int, cache_write: int, output: int) -> dict:
    return {
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
        "output_tokens": output,
    }


def assistant_entry(message_id: str, **overrides: Any) -> dict:
    entry = {
        "type": "assistant",
        "uuid": f"uuid-{message_id}",
        "timestamp": "2026-10-16T22:00:00.000Z",
        "effort": "max",
        "isSidechain": False,
        "message": {
            "id": message_id,
            "model": MODEL,
            "content": [{"type": "text", "text": "hola"}],
            "usage": usage(10, 100, 5, 20),
        },
    }
    entry.update(overrides)
    return entry


def jsonl(*entries: dict) -> str:
    return "".join(json.dumps(entry) + "\n" for entry in entries)


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime.fromisoformat("2026-10-16T19:40:00+00:00")

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class HookTestCase(unittest.TestCase):
    """Runs hooks in-process against a throw-away project directory."""

    def setUp(self) -> None:
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        self.project = Path(workdir.name)
        environment = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.project)})
        environment.start()
        self.addCleanup(environment.stop)
        self.transcript = self.project / "transcript.jsonl"
        self.transcript.write_text("")
        self.clock = FakeClock()
        clock_patch = mock.patch.object(devlog, "now", self.clock)
        clock_patch.start()
        self.addCleanup(clock_patch.stop)

    @property
    def devlog_path(self) -> Path:
        return self.project / "DEV-LOG.md"

    @property
    def state_dir(self) -> Path:
        return self.project / ".claude" / "devlog" / SESSION_ID

    @property
    def log(self) -> str:
        return self.devlog_path.read_text("utf-8") if self.devlog_path.exists() else ""

    def fire(self, event: str, **fields: Any) -> None:
        payload = {
            "hook_event_name": event,
            "session_id": SESSION_ID,
            "transcript_path": str(self.transcript),
            "cwd": str(self.project),
            **fields,
        }
        devlog.dispatch(payload)

    def append_transcript(self, *entries: dict) -> None:
        with self.transcript.open("a", encoding="utf-8") as handle:
            handle.write(jsonl(*entries))

    def submit(self, prompt: str) -> None:
        self.fire("UserPromptSubmit", prompt=prompt)

    def use_tool(self, name: str, tool_input: dict, **fields: Any) -> None:
        self.fire("PostToolUse", tool_name=name, tool_input=tool_input, **fields)

    def stop(self, message: str = "Listo.") -> None:
        self.fire("Stop", last_assistant_message=message)

    def events(self) -> list[dict]:
        return devlog.parse_json_lines((self.state_dir / "events.jsonl").read_text("utf-8"))


class RedactionTests(unittest.TestCase):
    def assert_masked(self, secret: str) -> None:
        self.assertNotIn(secret, devlog.redact(f"antes {secret} después"))

    def test_anthropic_key(self) -> None:
        self.assert_masked(make_secret("sk-ant-api03-", 60))

    def test_long_generic_sk_key(self) -> None:
        self.assert_masked(make_secret("sk-", 40))

    def test_github_tokens_of_every_kind(self) -> None:
        for kind in "pousr":
            with self.subTest(kind=kind):
                self.assert_masked(make_secret(f"gh{kind}_", 36))

    def test_github_fine_grained_token(self) -> None:
        self.assert_masked(make_secret("github_pat_", 40))

    def test_aws_access_key(self) -> None:
        self.assert_masked("AKIA" + "AB12CD34EF56GH78")

    def test_slack_token(self) -> None:
        self.assert_masked("xox" + "b-123456789012-abcdefghijkl")

    def test_context7_key(self) -> None:
        self.assert_masked(make_secret("ctx7sk-", 36))

    def test_jwt(self) -> None:
        jwt = "eyJ" + "hbGciOiJIUzI1NiJ9.eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123_-xyz"
        self.assert_masked(jwt)

    def test_private_key_block(self) -> None:
        begin = "-----BEGIN " + "RSA PRIVATE KEY-----"
        end = "-----END " + "RSA PRIVATE KEY-----"
        text = f"{begin}\nMIIEvQIBADANBg\n{end}\ntexto posterior"
        self.assertEqual(devlog.redact(text), f"{devlog.MASK}\ntexto posterior")

    def test_private_key_without_end_marker_is_masked_to_the_end(self) -> None:
        text = "-----BEGIN " + "PRIVATE KEY-----\nMIIEvQIBADANBg"
        self.assertEqual(devlog.redact(text), devlog.MASK)

    def test_assignment_keeps_key_and_masks_value(self) -> None:
        self.assertEqual(devlog.redact("api_key = hunter2"), "api_key = ***")

    def test_assignment_with_colon_and_quotes(self) -> None:
        self.assertEqual(devlog.redact('"password": "my pass phrase"'), '"password": ***')

    def test_assignment_with_prefixed_env_name(self) -> None:
        self.assertEqual(devlog.redact("export ANTHROPIC_API_KEY=abc123"), "export ANTHROPIC_API_KEY=***")

    def test_assignment_passwd_and_secret(self) -> None:
        self.assertEqual(devlog.redact("passwd=x secret: y"), "passwd=*** secret: ***")

    def test_aws_secret_access_key_assignment(self) -> None:
        text = "export AWS_SECRET_ACCESS_KEY=" + make_secret("wJalr", 35)
        self.assertEqual(devlog.redact(text), "export AWS_SECRET_ACCESS_KEY=***")

    def test_bearer_authorization_header(self) -> None:
        text = "Authorization: Bearer " + make_secret("", 24)
        self.assertEqual(devlog.redact(text), "Authorization: ***")

    def test_credentials_embedded_in_a_url(self) -> None:
        text = "postgres://app:" + make_secret("", 12) + "@host/db"
        self.assertEqual(devlog.redact(text), "postgres://***@host/db")

    def test_private_key_assignment(self) -> None:
        text = "private_key=" + make_secret("", 40)
        self.assertEqual(devlog.redact(text), "private_key=***")

    def test_url_with_a_port_is_not_a_credential(self) -> None:
        text = "http://localhost:8000/api"
        self.assertEqual(devlog.redact(text), text)

    def test_the_word_bearer_in_prose_is_not_a_secret(self) -> None:
        text = "bearer of bad news"
        self.assertEqual(devlog.redact(text), text)

    def test_token_counts_are_not_secrets(self) -> None:
        self.assertEqual(devlog.redact("tokens: 1200, max_tokens = 4096"), "tokens: 1200, max_tokens = 4096")

    def test_words_ending_in_sk_are_not_secrets(self) -> None:
        text = "task-management-system-for-long-names"
        self.assertEqual(devlog.redact(text), text)

    def test_large_blob_is_scanned_in_linear_time(self) -> None:
        blob = "eyJhbGciOiJIUzI1NiJ9" * 20_000
        started = time.perf_counter()
        devlog.redact(blob)
        self.assertLess(time.perf_counter() - started, 2.0)


class FormattingTests(unittest.TestCase):
    def test_compact_number(self) -> None:
        cases = {0: "0", 999: "999", 1200: "1.2k", 210_000: "210k", 3_400_000: "3.4M", 1_000_000: "1M"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(devlog.compact_number(value), expected)

    def test_format_duration(self) -> None:
        cases = {0: "0s", 45: "45s", 192: "3m 12s", 723: "12m 3s", 3900: "1h 5m"}
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(devlog.format_duration(seconds), expected)

    def test_display_path_inside_project_is_relative(self) -> None:
        self.assertEqual(devlog.display_path("/work/app/src/main.py", Path("/work/app")), "src/main.py")

    def test_display_path_inside_home_uses_tilde(self) -> None:
        raw = str(Path.home() / "notes" / "a.md")
        self.assertEqual(devlog.display_path(raw, Path("/work/app")), "~/notes/a.md")

    def test_display_path_elsewhere_is_unchanged(self) -> None:
        self.assertEqual(devlog.display_path("/etc/hosts", Path("/work/app")), "/etc/hosts")

    def test_display_path_relative_input_is_unchanged(self) -> None:
        self.assertEqual(devlog.display_path("src/a.py", Path("/work/app")), "src/a.py")

    def test_blockquote_prefixes_every_line(self) -> None:
        self.assertEqual(devlog.blockquote("a\n\nb"), "> a\n>\n> b")

    def test_blockquote_of_empty_text(self) -> None:
        self.assertEqual(devlog.blockquote(""), ">")

    def test_clip_keeps_short_text(self) -> None:
        self.assertEqual(devlog.clip("abc", 3), "abc")

    def test_clip_appends_ellipsis(self) -> None:
        self.assertEqual(devlog.clip("abcd", 3), "abc…")


class ExclusionMarkerTests(unittest.TestCase):
    def test_phrase_is_detected(self) -> None:
        self.assertTrue(devlog.is_excluded("Haz X. No documentes este prompt."))

    def test_phrase_ignores_case(self) -> None:
        self.assertTrue(devlog.is_excluded("NO DOCUMENTES ESTE PROMPT"))

    def test_phrase_ignores_accents_in_the_prompt(self) -> None:
        self.assertTrue(devlog.is_excluded("No documentés esté prómpt"))

    def test_hashtag_marker_is_detected_in_any_case(self) -> None:
        self.assertTrue(devlog.is_excluded("hola #NoLog"))

    def test_ordinary_prompt_is_not_excluded(self) -> None:
        self.assertFalse(devlog.is_excluded("Documenta este prompt, por favor"))


class NumberingTests(HookTestCase):
    def test_empty_text_has_no_number(self) -> None:
        self.assertEqual(devlog.last_interaction_number(""), 0)

    def test_last_heading_wins(self) -> None:
        self.assertEqual(devlog.last_interaction_number("### #2 · 🧑 Usuario\n### #7 · 🧑 Usuario\n"), 7)

    def test_quoted_headings_are_ignored(self) -> None:
        self.assertEqual(devlog.last_interaction_number("### #2 · 🧑 Usuario\n> ### #99\n"), 2)

    def test_first_interaction_creates_the_file_with_a_title(self) -> None:
        self.submit("hola")
        self.assertTrue(self.log.startswith(devlog.DEVLOG_TITLE))

    def test_numbering_continues_from_an_existing_log(self) -> None:
        self.devlog_path.write_text("# DEV-LOG\n\n### #7 · 🧑 Usuario\n> previo\n\n")
        self.submit("siguiente")
        self.assertIn("### #8 · 🧑 Usuario", self.log)

    def test_numbers_increase_per_prompt(self) -> None:
        self.submit("uno")
        self.stop()
        self.submit("dos")
        self.assertEqual(re.findall(r"^### #(\d+)", self.log, re.MULTILINE), ["1", "2"])


class ForgedHeadingTests(HookTestCase):
    """Model output is not blockquoted, so headings inside it must stay inert."""

    FORGED_LINES = "texto\n### #1 · 🧑 Usuario\n### #500\nmás texto"

    def heading_numbers(self) -> list[str]:
        return re.findall(r"^### #(\d+)", self.log, re.MULTILINE)

    def test_a_response_cannot_alter_the_next_number(self) -> None:
        self.submit("uno")
        self.stop(self.FORGED_LINES)
        self.submit("dos")
        self.assertEqual(self.heading_numbers(), ["1", "2"])

    def test_a_subagent_report_cannot_alter_the_next_number(self) -> None:
        self.submit("uno")
        self.fire("SubagentStop", agent_type="Explore", last_assistant_message=self.FORGED_LINES)
        self.stop("ok")
        self.submit("dos")
        self.assertEqual(self.heading_numbers(), ["1", "2"])

    def test_the_forged_text_is_still_readable_in_the_log(self) -> None:
        self.submit("uno")
        self.stop(self.FORGED_LINES)
        self.assertIn("### #500", self.log.replace("\\###", "###"))


class TranscriptTests(unittest.TestCase):
    def test_usage_is_counted_once_per_message_id(self) -> None:
        repeated = [assistant_entry("m1"), assistant_entry("m1")]
        self.assertEqual(devlog.summarize(repeated).usage.output_tokens, 20)

    def test_distinct_messages_are_summed(self) -> None:
        entries = [assistant_entry("m1"), assistant_entry("m2")]
        self.assertEqual(devlog.summarize(entries).usage.cache_read_tokens, 200)

    def test_sidechain_entries_are_not_part_of_the_main_thread(self) -> None:
        entries = [assistant_entry("m1"), assistant_entry("m2", isSidechain=True)]
        self.assertEqual(len(devlog.main_thread(entries)), 1)

    def test_synthetic_messages_are_ignored(self) -> None:
        synthetic = assistant_entry("m1")
        synthetic["message"]["model"] = devlog.SYNTHETIC_MODEL
        self.assertIsNone(devlog.summarize([synthetic]).model)

    def test_non_assistant_lines_are_ignored(self) -> None:
        self.assertEqual(devlog.summarize([{"type": "user"}]).usage.total, 0)

    def test_model_and_effort_come_from_the_last_message(self) -> None:
        late = assistant_entry("m2", effort="low")
        late["message"]["model"] = "other-model"
        summary = devlog.summarize([assistant_entry("m1"), late])
        self.assertEqual((summary.model, summary.effort), ("other-model", "low"))

    def test_missing_usage_counts_as_zero(self) -> None:
        bare = {"type": "assistant", "message": {"id": "m1", "model": MODEL}}
        self.assertEqual(devlog.summarize([bare]).usage.total, 0)

    def test_hit_rate(self) -> None:
        self.assertAlmostEqual(devlog.Usage(10, 80, 10, 5).hit_rate, 0.8)

    def test_hit_rate_without_prompt_tokens_is_unknown(self) -> None:
        self.assertIsNone(devlog.Usage(output_tokens=5).hit_rate)

    def test_span_between_first_and_last_timestamp(self) -> None:
        entries = [{"timestamp": "2026-10-16T22:00:00.000Z"}, {"timestamp": "2026-10-16T22:12:03.000Z"}]
        self.assertEqual(devlog.span_seconds(entries), 723)

    def test_span_of_a_single_entry_is_unknown(self) -> None:
        self.assertIsNone(devlog.span_seconds([{"timestamp": "2026-10-16T22:00:00.000Z"}]))


class ReadEntriesTests(unittest.TestCase):
    def setUp(self) -> None:
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        self.path = Path(workdir.name) / "t.jsonl"

    def test_reads_only_after_the_offset(self) -> None:
        first = jsonl({"n": 1})
        self.path.write_text(first + jsonl({"n": 2}))
        entries, _ = devlog.read_entries(str(self.path), len(first.encode()))
        self.assertEqual(entries, [{"n": 2}])

    def test_returns_the_end_offset(self) -> None:
        self.path.write_text(jsonl({"n": 1}))
        _, end = devlog.read_entries(str(self.path), 0)
        self.assertEqual(end, self.path.stat().st_size)

    def test_an_unfinished_last_line_is_left_for_later(self) -> None:
        complete = jsonl({"n": 1})
        self.path.write_text(complete + '{"n": 2')
        entries, end = devlog.read_entries(str(self.path), 0)
        self.assertEqual((entries, end), ([{"n": 1}], len(complete.encode())))

    def test_malformed_lines_are_skipped(self) -> None:
        self.path.write_text("garbage\n" + jsonl({"n": 1}))
        self.assertEqual(devlog.read_entries(str(self.path), 0)[0], [{"n": 1}])

    def test_raw_unicode_line_separator_does_not_split_a_record(self) -> None:
        self.path.write_text('{"text": "a b"}\n', encoding="utf-8")
        self.assertEqual(devlog.read_entries(str(self.path), 0)[0], [{"text": "a b"}])

    def test_missing_file_yields_nothing(self) -> None:
        self.assertEqual(devlog.read_entries(str(self.path), 7), ([], 7))

    def test_missing_path_yields_nothing(self) -> None:
        self.assertEqual(devlog.read_entries(None, 0), ([], 0))


class SessionHeaderTests(HookTestCase):
    def test_startup_header_has_no_date_or_time(self) -> None:
        self.fire("SessionStart", source="startup", model=MODEL)
        self.assertIn(f"## 🛰️ Sesión `2680e3d9` · startup · `{MODEL}`\n", self.log)

    def test_header_without_model(self) -> None:
        self.fire("SessionStart", source="clear")
        self.assertIn("## 🛰️ Sesión `2680e3d9` · clear\n", self.log)

    def test_resume_adds_the_cache_line(self) -> None:
        self.fire(
            "SessionStart",
            source="resume",
            prompt_cache_likely_expired=True,
            context_tokens=182_000,
            estimated_cache_write_usd=1.14,
        )
        expected = "- **Cache:** probablemente expirado · contexto 182k tokens · re-escritura estimada US$1.14"
        self.assertIn(expected, self.log)

    def test_resume_cache_line_reports_idle_time(self) -> None:
        self.fire("SessionStart", source="resume", seconds_since_last_response=3900)
        self.assertIn("inactivo 1h 5m", self.log)

    def test_startup_never_shows_the_cache_line(self) -> None:
        self.fire("SessionStart", source="startup", context_tokens=5000)
        self.assertNotIn("Cache", self.log)

    def test_resume_without_cache_fields_adds_no_line(self) -> None:
        self.fire("SessionStart", source="resume")
        self.assertNotIn("Cache", self.log)

    def test_compact_source_writes_no_header(self) -> None:
        self.fire("SessionStart", source="compact")
        self.assertEqual(self.log, "")

    def test_session_end_line(self) -> None:
        self.fire("SessionEnd", reason="clear")
        self.assertIn("*Sesión finalizada (clear)*", self.log)

    def test_session_end_without_reason(self) -> None:
        self.fire("SessionEnd")
        self.assertIn("*Sesión finalizada*", self.log)


class PromptBlockTests(HookTestCase):
    def test_prompt_heading_has_no_date_or_time(self) -> None:
        self.submit("hola")
        self.assertIn("### #1 · 🧑 Usuario\n> hola\n", self.log)

    def test_prompt_is_quoted_line_by_line(self) -> None:
        self.submit("línea 1\nlínea 2")
        self.assertIn("> línea 1\n> línea 2\n", self.log)

    def test_prompt_secrets_are_redacted(self) -> None:
        secret = make_secret("ghp_", 36)
        self.submit(f"usa {secret}")
        self.assertNotIn(secret, self.log)

    def test_short_prompt_has_no_details_block(self) -> None:
        self.submit("a" * devlog.PROMPT_PREVIEW_CHARS)
        self.assertNotIn("<details>", self.log)

    def test_long_prompt_is_previewed_with_an_ellipsis(self) -> None:
        self.submit("b" * (devlog.PROMPT_PREVIEW_CHARS + 1))
        self.assertIn("> " + "b" * devlog.PROMPT_PREVIEW_CHARS + "…\n", self.log)

    def test_long_prompt_keeps_the_full_text_in_details(self) -> None:
        self.submit("c" * (devlog.PROMPT_PREVIEW_CHARS + 50))
        self.assertIn("<details><summary>Prompt completo</summary>", self.log)
        self.assertIn("> " + "c" * (devlog.PROMPT_PREVIEW_CHARS + 50), self.log)

    def test_a_secret_straddling_the_preview_limit_is_never_exposed(self) -> None:
        secret = make_secret("sk-", 60)
        padding = "d" * (devlog.PROMPT_PREVIEW_CHARS - 20)
        self.submit(f"{padding} {secret}")
        self.assertNotIn(secret[:30], self.log)

    def test_the_prompt_is_written_before_the_turn_ends(self) -> None:
        self.submit("sobrevive a una caída")
        self.assertIn("sobrevive a una caída", self.log)


class HarnessMessageTests(HookTestCase):
    """Agent reports and notifications arrive as prompts but are not the user's."""

    AGENT_MESSAGE = '<agent-message from="general-purpose">[Subagent hand-back] informe</agent-message>'

    def setUp(self) -> None:
        super().setUp()
        self.interaction_file = self.state_dir / "interaction.json"

    def open_interaction_then_receive_message(self) -> None:
        self.submit("prompt real")
        self.stop("primera respuesta")
        self.submit(self.AGENT_MESSAGE)

    def test_a_message_opens_no_new_interaction(self) -> None:
        self.open_interaction_then_receive_message()
        self.stop("respuesta al informe")
        self.assertEqual(len(re.findall(r"^### #", self.log, re.MULTILINE)), 1)

    def test_the_following_stop_adds_a_continuation_block(self) -> None:
        self.open_interaction_then_receive_message()
        self.stop("respuesta al informe")
        self.assertIn("#### 🤖 Claude · continuación", self.log)

    def test_the_message_text_is_never_written_to_the_log(self) -> None:
        self.open_interaction_then_receive_message()
        self.assertNotIn("hand-back", self.log)

    def test_the_open_interaction_state_is_not_reset(self) -> None:
        self.submit("prompt real")
        before = self.interaction_file.read_text()
        self.submit(self.AGENT_MESSAGE)
        self.assertEqual(self.interaction_file.read_text(), before)

    def test_events_of_the_open_interaction_are_kept(self) -> None:
        self.submit("prompt real")
        self.use_tool("Edit", {"file_path": str(self.project / "a.py")})
        self.submit(self.AGENT_MESSAGE)
        self.stop("respuesta")
        self.assertIn("- **Archivos modificados:** `a.py`", self.log)

    def test_without_an_open_interaction_nothing_is_written(self) -> None:
        self.submit(self.AGENT_MESSAGE)
        self.assertEqual(self.log, "")

    def test_without_an_open_interaction_no_state_is_created(self) -> None:
        self.submit(self.AGENT_MESSAGE)
        self.assertFalse(self.interaction_file.exists())

    def test_a_stop_after_a_message_without_interaction_writes_nothing(self) -> None:
        self.submit(self.AGENT_MESSAGE)
        self.stop("respuesta huérfana")
        self.assertEqual(self.log, "")

    def test_every_harness_prefix_is_ignored(self) -> None:
        for prefix in devlog.HARNESS_MESSAGE_PREFIXES:
            with self.subTest(prefix=prefix):
                self.submit(f"{prefix} from=x]")
                self.assertEqual(self.log, "")

    def test_leading_whitespace_before_the_prefix_is_ignored(self) -> None:
        self.submit("  \n" + self.AGENT_MESSAGE)
        self.assertEqual(self.log, "")

    def test_a_real_prompt_mentioning_agent_message_midway_is_logged(self) -> None:
        self.submit("Explica qué es un <agent-message> en el harness")
        self.assertIn("### #1 · 🧑 Usuario\n> Explica qué es un <agent-message>", self.log)


class BlockSeparationTests(HookTestCase):
    def append_to_existing(self, existing: str) -> str:
        self.devlog_path.write_text(existing)
        devlog.append_to_devlog(self.devlog_path, "bloque\n\n")
        return self.log

    def test_a_single_trailing_newline_gets_a_blank_line(self) -> None:
        self.assertEqual(self.append_to_existing("texto\n"), "texto\n\nbloque\n\n")

    def test_no_trailing_newline_gets_a_blank_line(self) -> None:
        self.assertEqual(self.append_to_existing("texto"), "texto\n\nbloque\n\n")

    def test_an_existing_blank_line_is_not_doubled(self) -> None:
        self.assertEqual(self.append_to_existing("texto\n\n"), "texto\n\nbloque\n\n")

    def test_a_new_prompt_is_not_glued_to_the_previous_line(self) -> None:
        self.devlog_path.write_text("# DEV-LOG\n\n### #1 · 🧑 Usuario\n> hola\n")
        self.submit("siguiente")
        self.assertIn("> hola\n\n### #2 · 🧑 Usuario", self.log)

    def test_a_new_file_starts_with_the_title_only(self) -> None:
        devlog.append_to_devlog(self.devlog_path, "bloque\n\n")
        self.assertEqual(self.log, devlog.DEVLOG_TITLE + "bloque\n\n")

    def test_multibyte_trailing_text_is_handled(self) -> None:
        self.assertEqual(self.append_to_existing("sesión ñ\n"), "sesión ñ\n\nbloque\n\n")


class FullFlowTests(HookTestCase):
    """SessionStart -> UserPromptSubmit -> tools -> SubagentStop -> Stop."""

    def setUp(self) -> None:
        super().setUp()
        self.append_transcript(assistant_entry("previous", message={"id": "previous", "model": "old", "usage": usage(999_999, 0, 0, 0)}))
        self.fire("SessionStart", source="startup", model=MODEL)
        self.submit("Implementa X\nusa token = abc123secret")
        self.clock.advance(10)
        self.use_tool("Edit", {"file_path": str(self.project / "apps/api/main.py")})
        self.use_tool("Write", {"file_path": str(self.project / "README.md")})
        self.use_tool("Edit", {"file_path": str(self.project / "apps/api/main.py")})
        self.use_tool("Read", {"file_path": "/etc/hosts"})
        self.use_tool("Read", {"file_path": "/etc/hosts"})
        self.use_tool(
            "Bash",
            {"command": 'git commit -m "feat(api): mensaje"', "description": "Commit"},
            tool_response={"stdout": "[main abc1234] feat(api): mensaje\n 1 file changed"},
        )
        self.use_tool(
            "Bash",
            {"command": "gh pr create --fill"},
            tool_response={"stdout": "https://github.com/acme/app/pull/12\n"},
        )
        self.fire_subagent_stop()
        self.append_transcript(
            assistant_entry("m1", message=self.message("m1", usage(1000, 90_000, 5000, 2000))),
            assistant_entry("m1", message=self.message("m1", usage(1000, 90_000, 5000, 2000))),
            assistant_entry("m2", message=self.message("m2", usage(200, 100_000, 4000, 1400))),
            assistant_entry("side", isSidechain=True, message=self.message("side", usage(7_000_000, 0, 0, 0))),
        )
        self.clock.advance(182)
        self.stop("Hecho: **X** implementado.")

    def message(self, message_id: str, token_usage: dict) -> dict:
        return {"id": message_id, "model": MODEL, "content": [], "usage": token_usage}

    def fire_subagent_stop(self) -> None:
        agent_transcript = self.project / "agent.jsonl"
        usage_entry = assistant_entry(
            "a1",
            isSidechain=True,
            timestamp="2026-10-16T22:00:00.000Z",
            message={"id": "a1", "model": SUBAGENT_MODEL, "usage": usage(200_000, 900_000, 50_000, 50_000)},
        )
        last_entry = assistant_entry("a2", isSidechain=True, timestamp="2026-10-16T22:12:03.000Z")
        last_entry["message"]["model"] = SUBAGENT_MODEL
        last_entry["message"]["usage"] = usage(0, 0, 0, 0)
        agent_transcript.write_text(jsonl(usage_entry, last_entry))
        self.fire(
            "SubagentStop",
            agent_id="agent-1",
            agent_type="general-purpose",
            agent_transcript_path=str(agent_transcript),
            last_assistant_message="Reporte del subagente.",
        )

    def test_session_header(self) -> None:
        self.assertIn(f"## 🛰️ Sesión `2680e3d9` · startup · `{MODEL}`", self.log)

    def test_prompt_heading_and_redacted_text(self) -> None:
        self.assertIn("### #1 · 🧑 Usuario\n> Implementa X\n> usa token = ***\n", self.log)

    def test_response_heading_with_model_effort_and_duration(self) -> None:
        self.assertIn(f"#### 🤖 Claude · `{MODEL}` · esfuerzo max · ⏱ 3m 12s", self.log)

    def test_tools_are_counted_most_frequent_first(self) -> None:
        self.assertIn("- **Herramientas:** Edit ×2 · Read ×2 · Bash ×2 · Write ×1", self.log)

    def test_modified_files_are_unique_and_relative(self) -> None:
        self.assertIn("- **Archivos modificados:** `apps/api/main.py`, `README.md`", self.log)

    def test_git_line_has_commit_and_pull_request(self) -> None:
        expected = "- **Git:** `abc1234` feat(api): mensaje · PR https://github.com/acme/app/pull/12"
        self.assertIn(expected, self.log)

    def test_subagent_line(self) -> None:
        expected = f"- **Subagentes:** `general-purpose` · `{SUBAGENT_MODEL}` · ⏱ 12m 3s · 1.2M tokens"
        self.assertIn(expected, self.log)

    def test_tokens_exclude_previous_turns_and_sidechains(self) -> None:
        expected = "- **Tokens:** entrada 1.2k · cache leída 190k · cache escrita 9k · salida 3.4k · hit 95%"
        self.assertIn(expected, self.log)

    def test_final_response_in_details(self) -> None:
        self.assertIn("<details><summary>Respuesta</summary>\n\nHecho: **X** implementado.\n\n</details>", self.log)

    def test_subagent_report_in_details(self) -> None:
        expected = "<details><summary>Reporte del subagente general-purpose</summary>\n\nReporte del subagente.\n\n</details>"
        self.assertIn(expected, self.log)

    def test_log_contains_no_date_or_time(self) -> None:
        self.assertIsNone(TIME_OF_DAY.search(self.log))
        self.assertIsNone(CALENDAR_DATE.search(self.log))

    def test_events_are_cleared_after_stop(self) -> None:
        self.assertFalse((self.state_dir / "events.jsonl").exists())

    def test_the_interaction_stays_open_after_stop(self) -> None:
        self.assertTrue((self.state_dir / "interaction.json").exists())

    def test_the_offset_is_advanced_after_stop(self) -> None:
        saved = json.loads((self.state_dir / "interaction.json").read_text())
        self.assertEqual(saved["transcript_offset"], self.transcript.stat().st_size)


class ToolEventTests(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.submit("hola")

    def last_event(self) -> dict:
        return self.events()[-1]

    def test_read_grep_and_glob_are_only_counted(self) -> None:
        for tool in ("Read", "Grep", "Glob"):
            with self.subTest(tool=tool):
                self.use_tool(tool, {"file_path": "/x", "pattern": "p"})
                self.assertNotIn("detail", self.last_event())

    def test_bash_detail_joins_description_and_first_line(self) -> None:
        self.use_tool("Bash", {"description": "Run tests", "command": "pytest -q\nsecond line"})
        self.assertEqual(self.last_event()["detail"], "Run tests — pytest -q")

    def test_bash_detail_is_clipped(self) -> None:
        self.use_tool("Bash", {"command": "echo " + "x" * 400})
        self.assertEqual(len(self.last_event()["detail"]), devlog.DETAIL_MAX_CHARS + 1)

    def test_bash_detail_is_redacted(self) -> None:
        self.use_tool("Bash", {"command": "export API_KEY=hunter2"})
        self.assertEqual(self.last_event()["detail"], "export API_KEY=***")

    def test_agent_detail(self) -> None:
        tool_input = {"subagent_type": "Explore", "model": "sonnet", "description": "Busca usos"}
        self.use_tool("Agent", tool_input)
        self.assertEqual(self.last_event()["detail"], "Explore · sonnet · Busca usos")

    def test_task_is_summarized_like_agent(self) -> None:
        self.use_tool("Task", {"subagent_type": "Plan"})
        self.assertEqual(self.last_event()["detail"], "Plan")

    def test_web_search_and_fetch(self) -> None:
        self.use_tool("WebSearch", {"query": "hooks de claude"})
        self.use_tool("WebFetch", {"url": "https://example.com/doc"})
        self.assertEqual([e["detail"] for e in self.events()[-2:]], ["hooks de claude", "https://example.com/doc"])

    def test_skill_name(self) -> None:
        self.use_tool("Skill", {"skill": "python-clean-code"})
        self.assertEqual(self.last_event()["detail"], "python-clean-code")

    def test_mcp_tool_is_recorded_by_name(self) -> None:
        self.use_tool("mcp__serena__find_symbol", {"name_path": "x"})
        self.assertEqual(self.last_event()["tool"], "mcp__serena__find_symbol")

    def test_notebook_edit_uses_the_notebook_path(self) -> None:
        self.use_tool("NotebookEdit", {"notebook_path": str(self.project / "n.ipynb")})
        self.assertEqual(self.last_event()["detail"], "n.ipynb")

    def test_subagent_tool_calls_carry_the_agent_id(self) -> None:
        self.use_tool("Read", {}, agent_id="agent-9")
        self.assertEqual(self.last_event()["agent_id"], "agent-9")

    def test_malformed_tool_input_is_tolerated(self) -> None:
        self.fire("PostToolUse", tool_name="Bash", tool_input="not a dict")
        self.assertEqual(self.last_event()["tool"], "Bash")

    def test_tool_response_as_plain_string_is_supported(self) -> None:
        self.use_tool("Bash", {"command": "git commit -m x"}, tool_response="[main 1234567] feat: x")
        self.assertEqual(self.events()[-1]["hash"], "1234567")

    def test_root_commit_output_is_parsed(self) -> None:
        stdout = "[main (root-commit) abcdef1] primer commit\n"
        self.use_tool("Bash", {"command": "git commit -m x"}, tool_response={"stdout": stdout})
        self.assertEqual(self.events()[-1]["message"], "primer commit")

    def test_commit_message_is_redacted(self) -> None:
        stdout = f"[main abcdef1] usa {make_secret('ghp_', 36)}\n"
        self.use_tool("Bash", {"command": "git commit -m x"}, tool_response={"stdout": stdout})
        self.assertIn(devlog.MASK, self.events()[-1]["message"])

    def test_a_command_that_is_not_a_commit_records_no_commit(self) -> None:
        self.use_tool("Bash", {"command": "git status"}, tool_response={"stdout": "[main abcdef1] x"})
        self.assertEqual([e["kind"] for e in self.events()], ["tool"])


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class CommitFallbackTests(HookTestCase):
    """Wrapped git output (e.g. rtk prints only "ok") carries no hash."""

    def setUp(self) -> None:
        super().setUp()
        clock_patch = mock.patch.object(devlog, "now", lambda: datetime.now().astimezone())
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.repo = self.project / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("a")
        self.git("add", "a.txt")
        self.submit("hola")

    def git(self, *args: str, **env: str) -> str:
        command = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args]
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True, check=True, env={**os.environ, **env})
        return done.stdout.strip()

    def fire_commit(self) -> None:
        self.fire(
            "PostToolUse",
            tool_name="Bash",
            tool_input={"command": "rtk git commit -m 'feat: fallback'"},
            tool_response={"stdout": "ok 1 file changed\nok"},
            cwd=str(self.repo),
        )

    def test_fresh_head_commit_is_recorded(self) -> None:
        self.git("commit", "-q", "-m", "feat: fallback")
        self.fire_commit()
        self.assertEqual(self.events()[-1]["hash"], self.git("rev-parse", "--short", "HEAD"))

    def test_the_same_commit_is_not_recorded_twice(self) -> None:
        self.git("commit", "-q", "-m", "feat: fallback")
        self.fire_commit()
        self.fire_commit()
        self.assertEqual([e["kind"] for e in self.events()].count("commit"), 1)

    def test_an_old_head_commit_means_the_command_failed(self) -> None:
        self.git("commit", "-q", "-m", "viejo", GIT_COMMITTER_DATE="2020-01-01T00:00:00", GIT_AUTHOR_DATE="2020-01-01T00:00:00")
        self.fire_commit()
        self.assertNotIn("commit", [e["kind"] for e in self.events()])

    def test_a_directory_that_is_not_a_repository_is_tolerated(self) -> None:
        self.fire(
            "PostToolUse",
            tool_name="Bash",
            tool_input={"command": "git commit -m x"},
            tool_response={"stdout": "ok"},
            cwd=str(self.project / "missing"),
        )
        self.assertEqual([e["kind"] for e in self.events()], ["tool"])


class ContinuationTests(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.submit("Lanza un subagente en segundo plano")
        self.append_transcript(assistant_entry("m1", timestamp="2026-10-16T22:00:00.000Z"))
        self.clock.advance(30)
        self.stop("Lo lancé; espero el resultado.")
        self.use_tool("Edit", {"file_path": str(self.project / "late.py")})
        self.append_transcript(
            assistant_entry("m2", timestamp="2026-10-16T23:00:00.000Z"),
            assistant_entry("m3", timestamp="2026-10-16T23:01:30.000Z"),
        )
        self.clock.advance(7200)
        self.stop("El subagente terminó: todo bien.")

    def test_continuation_block_is_appended_under_the_previous_interaction(self) -> None:
        self.assertEqual(len(re.findall(r"^### #", self.log, re.MULTILINE)), 1)

    def test_continuation_heading_uses_the_transcript_span_not_idle_time(self) -> None:
        self.assertIn(f"#### 🤖 Claude · continuación · `{MODEL}` · esfuerzo max · ⏱ 1m 30s", self.log)

    def test_first_block_is_not_marked_as_continuation(self) -> None:
        first_heading = re.search(r"^#### 🤖 Claude.*$", self.log, re.MULTILINE)
        self.assertNotIn("continuación", first_heading[0])

    def test_continuation_has_its_own_content(self) -> None:
        continuation = self.log.split("continuación", 1)[1]
        self.assertIn("`late.py`", continuation)

    def test_continuation_tokens_exclude_the_first_block(self) -> None:
        continuation = self.log.split("continuación", 1)[1]
        self.assertIn("salida 40", continuation)

    def test_continuation_response_is_logged(self) -> None:
        self.assertIn("El subagente terminó: todo bien.", self.log)

    def test_blocks_stay_in_order(self) -> None:
        self.assertLess(self.log.index("Lo lancé"), self.log.index("El subagente terminó"))

    def test_an_empty_stop_adds_nothing(self) -> None:
        before = self.log
        self.fire("Stop")
        self.assertEqual(self.log, before)

    def test_a_new_prompt_closes_the_previous_interaction(self) -> None:
        self.submit("otra cosa")
        self.stop("segunda respuesta")
        self.assertEqual(self.log.count("continuación"), 1)


class StopWithoutStateTests(HookTestCase):
    def test_nothing_is_written(self) -> None:
        self.stop("respuesta huérfana")
        self.assertFalse(self.devlog_path.exists())

    def test_an_existing_log_is_left_untouched(self) -> None:
        self.devlog_path.write_text("# DEV-LOG\n\n")
        self.stop("respuesta huérfana")
        self.assertEqual(self.log, "# DEV-LOG\n\n")

    def test_stray_events_are_discarded(self) -> None:
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "events.jsonl").write_text('{"kind": "tool", "tool": "Bash"}\n')
        self.stop()
        self.assertFalse((self.state_dir / "events.jsonl").exists())

    def test_tool_events_are_not_recorded_without_an_interaction(self) -> None:
        self.use_tool("Bash", {"command": "ls"})
        self.assertFalse((self.state_dir / "events.jsonl").exists())

    def test_a_new_session_forgets_the_previous_interaction(self) -> None:
        self.submit("hola")
        self.fire("SessionStart", source="startup")
        before = self.log
        self.stop("continuación tardía")
        self.assertEqual(self.log, before)


class ExclusionFlowTests(HookTestCase):
    def run_excluded_turn(self, prompt: str) -> None:
        self.submit(prompt)
        self.use_tool("Edit", {"file_path": str(self.project / "secret.py")})
        self.append_transcript(assistant_entry("m1"))
        self.stop("respuesta que no debe quedar")
        self.stop("continuación que no debe quedar")

    def test_marker_phrase_hides_the_whole_interaction(self) -> None:
        self.run_excluded_turn("Haz X. No documentes este prompt.")
        self.assertEqual(self.log, "")

    def test_marker_phrase_without_accents_and_in_capitals(self) -> None:
        self.run_excluded_turn("NO DOCUMENTES ESTE PROMPT")
        self.assertEqual(self.log, "")

    def test_marker_phrase_with_accents_stripped_from_the_prompt(self) -> None:
        self.run_excluded_turn("no documentés este prompt")
        self.assertEqual(self.log, "")

    def test_nolog_hashtag_hides_the_interaction(self) -> None:
        self.run_excluded_turn("haz X #nolog")
        self.assertEqual(self.log, "")

    def test_tool_events_are_not_recorded(self) -> None:
        self.submit("haz X #nolog")
        self.use_tool("Bash", {"command": "ls"})
        self.assertFalse((self.state_dir / "events.jsonl").exists())

    def test_subagent_and_compaction_events_are_not_recorded(self) -> None:
        self.submit("haz X #nolog")
        self.fire("SubagentStop", agent_type="Explore", last_assistant_message="reporte")
        self.fire("PreCompact", trigger="auto")
        self.assertFalse((self.state_dir / "events.jsonl").exists())

    def test_the_next_prompt_is_logged_normally(self) -> None:
        self.run_excluded_turn("haz X #nolog")
        self.submit("segundo prompt")
        self.assertIn("### #1 · 🧑 Usuario\n> segundo prompt", self.log)

    def test_the_next_response_is_logged_without_leaks(self) -> None:
        self.run_excluded_turn("haz X #nolog")
        self.submit("segundo prompt")
        self.stop("respuesta visible")
        self.assertNotIn("secret.py", self.log)
        self.assertIn("respuesta visible", self.log)

    def test_a_failed_save_cannot_leak_the_response_under_the_previous_interaction(self) -> None:
        self.submit("prompt normal")
        self.stop("respuesta normal")
        with (
            mock.patch.object(devlog, "save_interaction", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            self.submit("haz X #nolog")
        self.stop("respuesta que no debe quedar")
        self.assertNotIn("respuesta que no debe quedar", self.log)

    def test_a_prompt_that_only_resembles_the_marker_is_logged(self) -> None:
        self.submit("documenta este prompt")
        self.assertIn("documenta este prompt", self.log)


class CompactionTests(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.submit("trabajo largo")
        self.fire("PreCompact", trigger="auto")
        self.fire("SessionStart", source="compact")
        self.stop("seguimos")

    def test_the_compaction_is_reported_once(self) -> None:
        self.assertEqual(self.log.count("- **Contexto:** compactado (auto)"), 1)

    def test_compaction_writes_no_session_header(self) -> None:
        self.assertNotIn("Sesión", self.log)

    def test_a_compaction_without_a_pre_compact_event_is_still_reported(self) -> None:
        self.submit("otro")
        self.fire("SessionStart", source="compact")
        self.stop("listo")
        self.assertIn("- **Contexto:** compactado\n", self.log)


class ResponseBlockTests(HookTestCase):
    def test_response_without_transcript_still_has_a_heading(self) -> None:
        self.fire("UserPromptSubmit", prompt="hola", transcript_path="")
        self.clock.advance(5)
        self.fire("Stop", transcript_path="", last_assistant_message="ok")
        self.assertIn("#### 🤖 Claude · ⏱ 5s\n", self.log)

    def test_long_response_is_truncated_with_a_note(self) -> None:
        self.submit("hola")
        self.stop("z" * (devlog.RESPONSE_MAX_CHARS + 10))
        self.assertIn("_… truncado: 10 caracteres omitidos_", self.log)

    def test_response_at_the_limit_is_complete(self) -> None:
        self.submit("hola")
        self.stop("z" * devlog.RESPONSE_MAX_CHARS)
        self.assertNotIn("truncado", self.log)

    def test_response_secrets_are_redacted(self) -> None:
        secret = make_secret("sk-ant-api03-", 60)
        self.submit("hola")
        self.stop(f"clave {secret}")
        self.assertNotIn(secret, self.log)

    def test_subagent_report_secrets_are_redacted(self) -> None:
        secret = make_secret("ghp_", 36)
        self.submit("hola")
        self.fire("SubagentStop", agent_type="Explore", last_assistant_message=f"hallé {secret}")
        self.stop("ok")
        self.assertNotIn(secret, self.log)

    def test_several_subagents_are_listed_as_nested_bullets(self) -> None:
        self.submit("hola")
        self.fire("SubagentStop", agent_type="Explore")
        self.fire("SubagentStop", agent_type="Plan")
        self.stop("ok")
        self.assertIn("- **Subagentes:**\n  - `Explore`\n  - `Plan`\n", self.log)

    def test_lines_without_data_are_omitted(self) -> None:
        self.submit("hola")
        self.stop("ok")
        for label in ("Herramientas", "Archivos modificados", "Git", "Subagentes", "Tokens", "Contexto"):
            with self.subTest(label=label):
                self.assertNotIn(f"**{label}:**", self.log)


class RobustnessTests(unittest.TestCase):
    def setUp(self) -> None:
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        self.project = Path(workdir.name)

    def run_hook(self, stdin: str, project_dir: str | None = None) -> subprocess.CompletedProcess:
        environment = {"PATH": os.environ.get("PATH", "")}
        if project_dir:
            environment["CLAUDE_PROJECT_DIR"] = project_dir
        return subprocess.run(
            [sys.executable, "-I", str(HOOK_SCRIPT)],
            input=stdin,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )

    def error_log(self) -> str:
        return (self.project / ".claude" / "devlog" / "errors.log").read_text("utf-8")

    def test_malformed_json_exits_zero(self) -> None:
        self.assertEqual(self.run_hook("{not json", str(self.project)).returncode, 0)

    def test_malformed_json_prints_nothing(self) -> None:
        self.assertEqual(self.run_hook("{not json", str(self.project)).stdout, "")

    def test_malformed_json_is_logged_with_its_traceback(self) -> None:
        self.run_hook("{not json", str(self.project))
        self.assertIn("Traceback", self.error_log())

    def test_non_object_payload_exits_zero_and_is_logged(self) -> None:
        result = self.run_hook("[1, 2]", str(self.project))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertIn("TypeError", self.error_log())

    def test_empty_stdin_exits_zero(self) -> None:
        self.assertEqual(self.run_hook("", str(self.project)).returncode, 0)

    def test_without_any_project_directory_it_stays_silent(self) -> None:
        result = self.run_hook("garbage")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_project_directory_falls_back_to_the_payload_cwd(self) -> None:
        payload = {"hook_event_name": "SessionEnd", "session_id": "s", "cwd": str(self.project)}
        self.run_hook(json.dumps(payload))
        self.assertIn("Sesión finalizada", (self.project / "DEV-LOG.md").read_text("utf-8"))

    def test_unknown_event_is_ignored(self) -> None:
        result = self.run_hook(json.dumps({"hook_event_name": "Notification"}), str(self.project))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertFalse((self.project / "DEV-LOG.md").exists())

    def test_valid_prompt_through_the_script_writes_the_log_and_no_stdout(self) -> None:
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": "hola"}
        result = self.run_hook(json.dumps(payload), str(self.project))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertIn("> hola", (self.project / "DEV-LOG.md").read_text("utf-8"))

    def test_a_failing_handler_is_logged_and_does_not_escape(self) -> None:
        def explode(_: devlog.Context) -> None:
            raise RuntimeError("boom")

        payload = json.dumps({"hook_event_name": "Stop", "session_id": "s"})
        output = io.StringIO()
        with (
            mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.project)}),
            mock.patch.dict(devlog.HANDLERS, {"Stop": explode}),
            mock.patch.object(sys, "stdin", io.StringIO(payload)),
            contextlib.redirect_stdout(output),
        ):
            exit_code = devlog.main()
        self.assertEqual((exit_code, output.getvalue()), (0, ""))
        self.assertIn("RuntimeError: boom", self.error_log())

    def test_corrupt_state_file_is_tolerated(self) -> None:
        state_dir = self.project / ".claude" / "devlog" / "s"
        state_dir.mkdir(parents=True)
        (state_dir / "interaction.json").write_text("{broken")
        payload = {"hook_event_name": "Stop", "session_id": "s", "last_assistant_message": "x"}
        result = self.run_hook(json.dumps(payload), str(self.project))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_session_id_cannot_escape_the_state_directory(self) -> None:
        context = devlog.Context({"session_id": "../../evil"}, self.project)
        self.assertTrue(context.state_dir.is_relative_to(self.project / ".claude" / "devlog"))


if __name__ == "__main__":
    unittest.main()
