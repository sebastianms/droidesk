"""Claude Code hook that records every human<->AI interaction in DEV-LOG.md.

Reads the hook payload from stdin and dispatches on `hook_event_name`.
It never writes to stdout and always exits 0: in UserPromptSubmit the stdout is
injected into the model context and in Stop exit code 2 forces Claude to continue.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import traceback
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

JsonDict = dict[str, Any]

DEVLOG_FILENAME = "DEV-LOG.md"
DEVLOG_TITLE = "# DEV-LOG\n\n"
STATE_ROOT = Path(".claude") / "devlog"
ERROR_LOG_FILENAME = "errors.log"
INTERACTION_FILENAME = "interaction.json"
EVENTS_FILENAME = "events.jsonl"
UNKNOWN_SESSION = "unknown"

# A prompt containing any of these (ignoring case and accents) is never logged.
EXCLUSION_MARKERS = ("no documentes este prompt", "#nolog")
# The harness delivers agent reports and notifications as if the user had typed
# them, which fires UserPromptSubmit; they are model output, not user prompts.
HARNESS_MESSAGE_PREFIXES = (
    "<agent-message",
    "<cross-session-message",
    "<task-notification",
    "[SYSTEM NOTIFICATION",
)

PROMPT_PREVIEW_CHARS = 1500
RESPONSE_MAX_CHARS = 20_000
DETAIL_MAX_CHARS = 160
SHORT_SESSION_ID_CHARS = 8
COMMIT_FRESHNESS_SECONDS = 30
GIT_QUERY_TIMEOUT_SECONDS = 2
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
NUMBER_SCALES = (("M", 1_000_000), ("k", 1_000))
SYNTHETIC_MODEL = "<synthetic>"
MASK = "***"

FILE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
CACHE_SOURCES = frozenset({"resume", "fork"})

# Lookbehinds keep the scan linear and avoid hits inside words ("task-...").
SECRET_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        (
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"(?:[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----|[\s\S]*)"
        ),
        r"(?<![A-Za-z0-9])sk-ant-[\w-]{10,}",
        r"(?<![A-Za-z0-9])sk-[\w-]{20,}",
        r"gh[pousr]_[A-Za-z0-9]{20,}",
        r"github_pat_\w{20,}",
        r"AKIA[0-9A-Z]{16}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}",
        r"ctx7sk-[\w-]{10,}",
        r"(?<![\w-])eyJ[\w-]+\.[\w-]+\.[\w-]+",
        r"(?i:\bbearer)\s+[\w.~+/=-]{16,}",
        r"(?<=://)[^\s/:@]+:[^\s/@]+(?=@)",
    )
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?P<key>(?:api[_-]?key|secret(?:[_-]?(?:access[_-]?)?key)?|private[_-]?key"
    r"|token|password|passwd)(?!\w))"
    r"(?P<sep>[\"']?\s*[=:]\s*)"
    r"(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s\"',;]+)",
    re.IGNORECASE,
)

INTERACTION_HEADING = re.compile(r"^### #(\d+)", re.MULTILINE)
GIT_COMMIT_COMMAND = re.compile(r"\bgit\b[^\n|;&]*\bcommit\b")
GH_PR_CREATE_COMMAND = re.compile(r"\bgh\s+pr\s+create\b")
COMMIT_OUTPUT_LINE = re.compile(
    r"^\[[^\]]*?\s(?P<hash>[0-9a-f]{7,40})\]\s(?P<message>.+)$", re.MULTILINE
)
PULL_REQUEST_URL = re.compile(r"https://\S+/pull/\d+")


@dataclass(frozen=True)
class Context:
    payload: JsonDict
    project_dir: Path

    @property
    def devlog_path(self) -> Path:
        return self.project_dir / DEVLOG_FILENAME

    @property
    def state_dir(self) -> Path:
        session = str(self.payload.get("session_id") or UNKNOWN_SESSION)
        return self.project_dir / STATE_ROOT / re.sub(r"[^\w-]", "_", session)

    @property
    def interaction_path(self) -> Path:
        return self.state_dir / INTERACTION_FILENAME

    @property
    def events_path(self) -> Path:
        return self.state_dir / EVENTS_FILENAME

    @property
    def working_dir(self) -> Path:
        return Path(self.payload.get("cwd") or self.project_dir)


@dataclass
class Interaction:
    started_at: str
    transcript_offset: int
    number: int = 0
    responses: int = 0
    excluded: bool = False


@dataclass
class Usage:
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
            self.output_tokens + other.output_tokens,
        )

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
            + self.output_tokens
        )

    @property
    def hit_rate(self) -> float | None:
        prompt_tokens = (
            self.input_tokens + self.cache_read_tokens + self.cache_write_tokens
        )
        return self.cache_read_tokens / prompt_tokens if prompt_tokens else None


@dataclass
class TranscriptSummary:
    model: str | None
    effort: str | None
    usage: Usage


@dataclass
class TurnReport:
    summary: TranscriptSummary
    seconds: float | None
    events: list[JsonDict]
    response: str
    continuation: bool

    @property
    def has_content(self) -> bool:
        return bool(self.response or self.events or self.summary.usage.total)


# --- Small value helpers -----------------------------------------------------


def now() -> datetime:
    return datetime.now().astimezone()


def as_dict(value: Any) -> JsonDict:
    return value if isinstance(value, dict) else {}


def number_of(payload: JsonDict, key: str) -> float | None:
    value = payload.get(key)
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return value if is_number else None


def join_parts(parts: Iterable[str | None], separator: str = " · ") -> str:
    return separator.join(part for part in parts if part)


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def compact_number(value: int) -> str:
    for suffix, scale in NUMBER_SCALES:
        if value >= scale:
            return f"{value / scale:.1f}".removesuffix(".0") + suffix
    return str(value)


def format_duration(seconds: float) -> str:
    hours, rest = divmod(round(seconds), SECONDS_PER_HOUR)
    minutes, secs = divmod(rest, SECONDS_PER_MINUTE)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def blockquote(text: str) -> str:
    lines = text.splitlines() or [""]
    return "\n".join(f"> {line}".rstrip() for line in lines)


def display_path(raw: str, project_dir: Path) -> str:
    path = Path(raw)
    for base, prefix in ((project_dir, ""), (Path.home(), "~/")):
        if path.is_relative_to(base):
            return prefix + path.relative_to(base).as_posix()
    return raw


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return plain.casefold()


def is_harness_message(prompt: str) -> bool:
    return prompt.lstrip().startswith(HARNESS_MESSAGE_PREFIXES)


def is_excluded(prompt: str) -> bool:
    folded = fold(prompt)
    return any(fold(marker) in folded for marker in EXCLUSION_MARKERS)


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(MASK, text)
    return ASSIGNMENT_PATTERN.sub(r"\g<key>\g<sep>" + MASK, text)


def parse_json_lines(text: str) -> list[JsonDict]:
    # Not splitlines(): JSON strings may carry raw U+2028, which splitlines() cuts.
    records: list[JsonDict] = []
    for line in text.split("\n"):
        with suppress(ValueError):
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
    return records


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    # Python 3.10 cannot parse the trailing "Z" that transcripts use.
    iso_text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(iso_text)
    except ValueError:
        return None


# --- File IO -----------------------------------------------------------------


@contextmanager
def locked_append(path: Path) -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield handle


def append_text(path: Path, text: str) -> None:
    with locked_append(path) as handle:
        handle.write(text)


def paragraph_break(tail: bytes) -> str:
    """Newlines still missing so that a new block starts after a blank line."""
    if tail.endswith(b"\n\n"):
        return ""
    return "\n" if tail.endswith(b"\n") else "\n\n"


def start_block(handle: TextIO) -> None:
    """Write the title into a new file, or whatever separates the next block."""
    size = os.fstat(handle.fileno()).st_size
    if size == 0:
        handle.write(DEVLOG_TITLE)
        return
    tail = os.pread(handle.fileno(), len(b"\n\n"), max(size - len(b"\n\n"), 0))
    handle.write(paragraph_break(tail))


def append_to_devlog(path: Path, block: str) -> None:
    with locked_append(path) as handle:
        start_block(handle)
        handle.write(block)


def last_interaction_number(text: str) -> int:
    numbers = INTERACTION_HEADING.findall(text)
    return int(numbers[-1]) if numbers else 0


def append_numbered(path: Path, render: Callable[[int], str]) -> int:
    with locked_append(path) as handle:
        start_block(handle)
        handle.seek(0)
        number = last_interaction_number(handle.read()) + 1
        handle.write(render(number))
    return number


# --- Session state -----------------------------------------------------------


def load_interaction(ctx: Context) -> Interaction | None:
    try:
        return Interaction(**json.loads(ctx.interaction_path.read_text("utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def save_interaction(ctx: Context, interaction: Interaction) -> None:
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    ctx.interaction_path.write_text(json.dumps(asdict(interaction)), "utf-8")


def is_recording(ctx: Context) -> bool:
    interaction = load_interaction(ctx)
    return interaction is not None and not interaction.excluded


def read_events(ctx: Context) -> list[JsonDict]:
    try:
        return parse_json_lines(ctx.events_path.read_text("utf-8"))
    except OSError:
        return []


def append_events(ctx: Context, events: list[JsonDict]) -> None:
    lines = (json.dumps(event, ensure_ascii=False) + "\n" for event in events)
    append_text(ctx.events_path, "".join(lines))


def clear_events(ctx: Context) -> None:
    ctx.events_path.unlink(missing_ok=True)


def reset_state(ctx: Context) -> None:
    ctx.interaction_path.unlink(missing_ok=True)
    clear_events(ctx)


def timestamp() -> str:
    return now().isoformat(timespec="seconds")


# --- Transcript --------------------------------------------------------------


def transcript_size(ctx: Context) -> int:
    try:
        return os.path.getsize(str(ctx.payload.get("transcript_path") or ""))
    except OSError:
        return 0


def read_entries(raw_path: Any, offset: int) -> tuple[list[JsonDict], int]:
    """Parse the complete JSONL lines after `offset`; return them and the new offset."""
    if not isinstance(raw_path, str) or not raw_path:
        return [], offset
    try:
        with open(raw_path, "rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return [], offset
    complete = data[: data.rfind(b"\n") + 1]
    entries = parse_json_lines(complete.decode("utf-8", errors="replace"))
    return entries, offset + len(complete)


def main_thread(entries: list[JsonDict]) -> list[JsonDict]:
    return [entry for entry in entries if not entry.get("isSidechain")]


def assistant_messages(entries: list[JsonDict]) -> list[JsonDict]:
    """One entry per message.id (the last one): content blocks repeat the usage."""
    latest: dict[Any, JsonDict] = {}
    for index, entry in enumerate(entries):
        message = as_dict(entry.get("message"))
        if entry.get("type") != "assistant" or message.get("model") == SYNTHETIC_MODEL:
            continue
        latest[message.get("id") or entry.get("uuid") or index] = entry
    return list(latest.values())


def token_count(raw: JsonDict, key: str) -> int:
    value = raw.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def usage_of(entry: JsonDict) -> Usage:
    raw = as_dict(as_dict(entry.get("message")).get("usage"))
    return Usage(
        input_tokens=token_count(raw, "input_tokens"),
        cache_read_tokens=token_count(raw, "cache_read_input_tokens"),
        cache_write_tokens=token_count(raw, "cache_creation_input_tokens"),
        output_tokens=token_count(raw, "output_tokens"),
    )


def summarize(entries: list[JsonDict]) -> TranscriptSummary:
    messages = assistant_messages(entries)
    last = messages[-1] if messages else {}
    return TranscriptSummary(
        model=as_dict(last.get("message")).get("model"),
        effort=last.get("effort"),
        usage=sum((usage_of(message) for message in messages), Usage()),
    )


def span_seconds(entries: list[JsonDict]) -> float | None:
    moments = [parse_timestamp(entry.get("timestamp")) for entry in entries]
    known = [moment for moment in moments if moment]
    if len(known) < 2:
        return None
    return (max(known) - min(known)).total_seconds()


# --- Tool event summaries (PostToolUse) --------------------------------------


def written_path(ctx: Context, tool_input: JsonDict) -> str | None:
    raw = tool_input.get("file_path") or tool_input.get("notebook_path")
    return display_path(str(raw), ctx.project_dir) if raw else None


def shell_summary(_: Context, tool_input: JsonDict) -> str | None:
    lines = str(tool_input.get("command") or "").strip().splitlines()
    first_line = lines[0] if lines else None
    return join_parts([tool_input.get("description"), first_line], " — ")


def subagent_call_summary(_: Context, tool_input: JsonDict) -> str | None:
    keys = ("subagent_type", "model", "description")
    return join_parts(str(tool_input.get(key) or "") for key in keys)


def query_summary(_: Context, tool_input: JsonDict) -> str | None:
    return tool_input.get("query") or tool_input.get("url")


def skill_summary(_: Context, tool_input: JsonDict) -> str | None:
    return tool_input.get("skill") or tool_input.get("name")


TOOL_SUMMARIZERS: dict[str, Callable[[Context, JsonDict], str | None]] = {
    "Write": written_path,
    "Edit": written_path,
    "MultiEdit": written_path,
    "NotebookEdit": written_path,
    "Bash": shell_summary,
    "Agent": subagent_call_summary,
    "Task": subagent_call_summary,
    "WebSearch": query_summary,
    "WebFetch": query_summary,
    "Skill": skill_summary,
}


def summarize_tool(ctx: Context, tool: str, tool_input: JsonDict) -> str | None:
    summarizer = TOOL_SUMMARIZERS.get(tool)
    detail = summarizer(ctx, tool_input) if summarizer else None
    return clip(redact(str(detail)), DETAIL_MAX_CHARS) if detail else None


def tool_stdout(payload: JsonDict) -> str:
    response = payload.get("tool_response")
    if isinstance(response, dict):
        return str(response.get("stdout") or "")
    return str(response or "")


def commit_event(short_hash: str, message: str) -> JsonDict:
    return {"kind": "commit", "hash": short_hash, "message": redact(message)}


def commit_from_stdout(stdout: str) -> JsonDict | None:
    match = COMMIT_OUTPUT_LINE.search(stdout)
    return commit_event(match["hash"], match["message"]) if match else None


def recent_head_commit(ctx: Context) -> JsonDict | None:
    """Fallback for wrapped git output (e.g. rtk prints only "ok", no hash)."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h%x00%ct%x00%s"],
            cwd=ctx.working_dir,
            capture_output=True,
            text=True,
            timeout=GIT_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    fields = result.stdout.rstrip("\n").split("\0", 2)
    if result.returncode != 0 or len(fields) != 3:
        return None
    short_hash, committed_at, subject = fields
    if now().timestamp() - int(committed_at) > COMMIT_FRESHNESS_SECONDS:
        return None
    return commit_event(short_hash, subject)


def detect_commit(ctx: Context) -> JsonDict | None:
    commit = commit_from_stdout(tool_stdout(ctx.payload)) or recent_head_commit(ctx)
    known_hashes = {event.get("hash") for event in read_events(ctx)}
    return None if commit is None or commit["hash"] in known_hashes else commit


def detect_pull_request(ctx: Context) -> JsonDict | None:
    match = PULL_REQUEST_URL.search(tool_stdout(ctx.payload))
    return {"kind": "pr", "url": match[0]} if match else None


def shell_events(ctx: Context, command: str) -> list[JsonDict]:
    detections = []
    if GIT_COMMIT_COMMAND.search(command):
        detections.append(detect_commit(ctx))
    if GH_PR_CREATE_COMMAND.search(command):
        detections.append(detect_pull_request(ctx))
    return [event for event in detections if event]


# --- Rendering ---------------------------------------------------------------


def escape_interaction_headings(text: str) -> str:
    # Model output is not blockquoted: a line like "### #1" would be read back by
    # last_interaction_number() and corrupt the numbering of the next prompt.
    return INTERACTION_HEADING.sub(r"\\\g<0>", text)


def details_block(summary: str, body: str) -> str:
    safe_body = escape_interaction_headings(body)
    return f"<details><summary>{summary}</summary>\n\n{safe_body}\n\n</details>"


def render_session_header(payload: JsonDict) -> str:
    session_id = str(payload.get("session_id") or UNKNOWN_SESSION)
    short_id = session_id[:SHORT_SESSION_ID_CHARS]
    model = payload.get("model")
    return join_parts(
        [
            f"## 🛰️ Sesión `{short_id}`",
            payload.get("source"),
            f"`{model}`" if model else None,
        ]
    )


def describe_expiry(expired: Any) -> str | None:
    if expired is None:
        return None
    return "probablemente expirado" if expired else "probablemente vigente"


def render_cache_line(payload: JsonDict) -> str | None:
    idle = number_of(payload, "seconds_since_last_response")
    context = number_of(payload, "context_tokens")
    cost = number_of(payload, "estimated_cache_write_usd")
    details = join_parts(
        [
            describe_expiry(payload.get("prompt_cache_likely_expired")),
            None if idle is None else f"inactivo {format_duration(idle)}",
            None if context is None else f"contexto {compact_number(int(context))} tokens",
            None if cost is None else f"re-escritura estimada US${cost:.2f}",
        ]
    )
    return f"- **Cache:** {details}" if details else None


def render_prompt_block(number: int, prompt: str) -> str:
    heading = f"### #{number} · 🧑 Usuario"
    if len(prompt) <= PROMPT_PREVIEW_CHARS:
        return f"{heading}\n{blockquote(prompt)}\n\n"
    preview = blockquote(clip(prompt, PROMPT_PREVIEW_CHARS))
    full = details_block("Prompt completo", blockquote(prompt))
    return f"{heading}\n{preview}\n\n{full}\n\n"


def of_kind(events: list[JsonDict], kind: str) -> list[JsonDict]:
    return [event for event in events if event.get("kind") == kind]


def response_heading(report: TurnReport) -> str:
    summary = report.summary
    return join_parts(
        [
            "#### 🤖 Claude",
            "continuación" if report.continuation else None,
            f"`{summary.model}`" if summary.model else None,
            f"esfuerzo {summary.effort}" if summary.effort else None,
            None if report.seconds is None else f"⏱ {format_duration(report.seconds)}",
        ]
    )


def tools_lines(report: TurnReport) -> list[str]:
    names = [event["tool"] for event in of_kind(report.events, "tool") if event.get("tool")]
    if not names:
        return []
    counts = " · ".join(f"{name} ×{n}" for name, n in Counter(names).most_common())
    return [f"- **Herramientas:** {counts}"]


def files_lines(report: TurnReport) -> list[str]:
    paths = dict.fromkeys(
        event["detail"]
        for event in of_kind(report.events, "tool")
        if event.get("tool") in FILE_WRITE_TOOLS and event.get("detail")
    )
    if not paths:
        return []
    return ["- **Archivos modificados:** " + ", ".join(f"`{path}`" for path in paths)]


def git_lines(report: TurnReport) -> list[str]:
    commits = [f"`{e['hash']}` {e['message']}" for e in of_kind(report.events, "commit")]
    pulls = [f"PR {event['url']}" for event in of_kind(report.events, "pr")]
    items = commits + pulls
    return [f"- **Git:** {' · '.join(items)}"] if items else []


def describe_subagent(event: JsonDict) -> str:
    usage = Usage(**as_dict(event.get("tokens")))
    seconds = number_of(event, "seconds")
    return join_parts(
        [
            f"`{event.get('agent_type') or 'subagente'}`",
            f"`{event['model']}`" if event.get("model") else None,
            None if seconds is None else f"⏱ {format_duration(seconds)}",
            f"{compact_number(usage.total)} tokens" if usage.total else None,
        ]
    )


def subagents_lines(report: TurnReport) -> list[str]:
    descriptions = [describe_subagent(e) for e in of_kind(report.events, "subagent")]
    if len(descriptions) <= 1:
        return [f"- **Subagentes:** {item}" for item in descriptions]
    return ["- **Subagentes:**"] + [f"  - {item}" for item in descriptions]


def tokens_lines(report: TurnReport) -> list[str]:
    usage = report.summary.usage
    if not usage.total:
        return []
    hit = usage.hit_rate
    details = join_parts(
        [
            f"entrada {compact_number(usage.input_tokens)}",
            f"cache leída {compact_number(usage.cache_read_tokens)}",
            f"cache escrita {compact_number(usage.cache_write_tokens)}",
            f"salida {compact_number(usage.output_tokens)}",
            None if hit is None else f"hit {hit:.0%}",
        ]
    )
    return [f"- **Tokens:** {details}"]


def context_lines(report: TurnReport) -> list[str]:
    announced = [event.get("trigger") for event in of_kind(report.events, "compact")]
    completed = len(of_kind(report.events, "compact_done"))
    labels = [f"compactado ({trigger})" for trigger in announced]
    labels += ["compactado"] * max(0, completed - len(announced))
    return [f"- **Contexto:** {', '.join(labels)}"] if labels else []


BULLET_BUILDERS = (
    tools_lines,
    files_lines,
    git_lines,
    subagents_lines,
    tokens_lines,
    context_lines,
)


def clip_response(text: str) -> str:
    omitted = len(text) - RESPONSE_MAX_CHARS
    if omitted <= 0:
        return text
    return f"{text[:RESPONSE_MAX_CHARS]}\n\n_… truncado: {omitted} caracteres omitidos_"


def render_response_block(report: TurnReport) -> str:
    bullets = [line for build in BULLET_BUILDERS for line in build(report)]
    chunks = ["\n".join([response_heading(report), *bullets])]
    if report.response:
        chunks.append(details_block("Respuesta", report.response))
    for event in of_kind(report.events, "subagent"):
        if event.get("report"):
            summary = f"Reporte del subagente {event.get('agent_type') or ''}".strip()
            chunks.append(details_block(summary, event["report"]))
    return "\n\n".join(chunks) + "\n\n"


# --- Event handlers ----------------------------------------------------------


def handle_session_start(ctx: Context) -> None:
    payload = ctx.payload
    if payload.get("source") == "compact":
        if is_recording(ctx):
            append_events(ctx, [{"kind": "compact_done", "time": timestamp()}])
        return
    reset_state(ctx)
    shows_cache = payload.get("source") in CACHE_SOURCES
    cache_line = render_cache_line(payload) if shows_cache else None
    block = "\n\n".join(filter(None, [render_session_header(payload), cache_line]))
    append_to_devlog(ctx.devlog_path, block + "\n\n")


def handle_user_prompt_submit(ctx: Context) -> None:
    prompt = str(ctx.payload.get("prompt") or "")
    if is_harness_message(prompt):
        return
    # Dropping the previous state first guarantees that, if saving this prompt's
    # state fails, its response cannot be logged under the previous interaction.
    reset_state(ctx)
    opened = Interaction(started_at=timestamp(), transcript_offset=transcript_size(ctx))
    if is_excluded(prompt):
        save_interaction(ctx, replace(opened, excluded=True))
        return
    safe_prompt = redact(prompt)
    number = append_numbered(ctx.devlog_path, lambda n: render_prompt_block(n, safe_prompt))
    save_interaction(ctx, replace(opened, number=number))


def handle_post_tool_use(ctx: Context) -> None:
    if not is_recording(ctx):
        return
    payload = ctx.payload
    tool = str(payload.get("tool_name") or "")
    tool_input = as_dict(payload.get("tool_input"))
    detail = summarize_tool(ctx, tool, tool_input)
    event: JsonDict = {"kind": "tool", "time": timestamp(), "tool": tool}
    if payload.get("agent_id"):
        event["agent_id"] = payload["agent_id"]
    if detail:
        event["detail"] = detail
    extra = shell_events(ctx, str(tool_input.get("command") or "")) if tool == "Bash" else []
    append_events(ctx, [event, *extra])


def handle_subagent_stop(ctx: Context) -> None:
    if not is_recording(ctx):
        return
    payload = ctx.payload
    entries, _ = read_entries(payload.get("agent_transcript_path"), 0)
    summary = summarize(entries)
    report = clip_response(redact(str(payload.get("last_assistant_message") or "")))
    event = {
        "kind": "subagent",
        "time": timestamp(),
        "agent_type": payload.get("agent_type"),
        "agent_id": payload.get("agent_id"),
        "model": summary.model,
        "tokens": asdict(summary.usage),
        "seconds": span_seconds(entries),
        "report": report,
    }
    append_events(ctx, [event])


def handle_pre_compact(ctx: Context) -> None:
    if is_recording(ctx):
        event = {"kind": "compact", "trigger": ctx.payload.get("trigger")}
        append_events(ctx, [event])


def elapsed_since(started_at: str) -> float | None:
    started = parse_timestamp(started_at)
    return None if started is None else max(0.0, (now() - started).total_seconds())


def turn_seconds(interaction: Interaction, turn: list[JsonDict]) -> float | None:
    # A continuation starts when its first transcript line is written, not at the
    # previous Stop: the user may have been away for hours in between.
    if interaction.responses:
        return span_seconds(turn)
    return elapsed_since(interaction.started_at)


def log_response(ctx: Context, interaction: Interaction) -> None:
    payload = ctx.payload
    entries, end_offset = read_entries(
        payload.get("transcript_path"), interaction.transcript_offset
    )
    turn = main_thread(entries)
    report = TurnReport(
        summary=summarize(turn),
        seconds=turn_seconds(interaction, turn),
        events=read_events(ctx),
        response=clip_response(redact(str(payload.get("last_assistant_message") or ""))),
        continuation=interaction.responses > 0,
    )
    if report.has_content:
        append_to_devlog(ctx.devlog_path, render_response_block(report))
        interaction = replace(interaction, responses=interaction.responses + 1)
    save_interaction(ctx, replace(interaction, transcript_offset=end_offset))


def handle_stop(ctx: Context) -> None:
    interaction = load_interaction(ctx)
    if interaction is not None and not interaction.excluded:
        log_response(ctx, interaction)
    clear_events(ctx)


def handle_session_end(ctx: Context) -> None:
    reason = ctx.payload.get("reason")
    label = f"Sesión finalizada ({reason})" if reason else "Sesión finalizada"
    append_to_devlog(ctx.devlog_path, f"*{label}*\n\n")


HANDLERS: dict[str, Callable[[Context], None]] = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PostToolUse": handle_post_tool_use,
    "SubagentStop": handle_subagent_stop,
    "PreCompact": handle_pre_compact,
    "Stop": handle_stop,
    "SessionEnd": handle_session_end,
}


# --- Entry point -------------------------------------------------------------


def resolve_project_dir(payload: JsonDict) -> Path | None:
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    return Path(raw) if isinstance(raw, str) and raw else None


def dispatch(payload: JsonDict) -> None:
    handler = HANDLERS.get(payload.get("hook_event_name"))
    project_dir = resolve_project_dir(payload)
    if handler and project_dir:
        handler(Context(payload, project_dir))


def log_error(payload: JsonDict) -> None:
    # Last resort: there is nobody left to report to, so the hook stays silent.
    with suppress(Exception):
        project_dir = resolve_project_dir(payload)
        if project_dir is None:
            return
        event = payload.get("hook_event_name", "?")
        entry = f"{timestamp()} {event}\n{traceback.format_exc()}\n"
        append_text(project_dir / STATE_ROOT / ERROR_LOG_FILENAME, entry)


def read_payload(stream: TextIO) -> JsonDict:
    payload = json.loads(stream.read())
    if not isinstance(payload, dict):
        raise TypeError("hook payload must be a JSON object")
    return payload


def main() -> int:
    payload: JsonDict = {}
    try:
        payload = read_payload(sys.stdin)
        dispatch(payload)
    except Exception:  # noqa: BLE001 - a hook must never fail the session
        log_error(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
