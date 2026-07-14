"""Custom ContextCite partitioner for markdown RAG context.

Splits a context string into attribution "sources" by markdown structure:

* Seperated by headers (lines starting with ``#``), headers are dropped from ablation sources
* Each list item (``-``/``*``/``+`` bullet or ``1.``/``1)`` numbered item) is its own source.
* A markdown table (a run of ``|``-delimited rows containing a ``---`` delimiter
  row) stays intact as a single atomic source
* Any remaining plain text is split into sentences
  using nltk sentence tokenizer (ContextCite default).
"""

from __future__ import annotations

import re
from typing import List, Optional

import nltk
import numpy as np
from numpy.typing import NDArray

from context_cite.context_partitioner import BaseContextPartitioner

# A markdown ATX header line: optional leading whitespace, 1-6 '#', then a space
# or end of line (so a bare "####" still counts, but "#hashtag" does not).
_HEADER_RE = re.compile(r"^[ \t]*#{1,6}(?:\s|$)")

# Strip header lines (incl. their trailing newline) out of separator text.
_HEADER_LINE_RE = re.compile(r"(?m)^[ \t]*#{1,6}(?:\s[^\n]*)?\n?")

# List marker at the start of a line: bullet (-, *, +) or numbered (1. / 1)).
_LIST_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])\s+")

# Table delimiter row, e.g. "| --- | :--: |" or "|---|---|".
_TABLE_DELIM_RE = re.compile(r"^[ \t]*\|?[ \t:|-]*-{2,}[ \t:|-]*\|?[ \t]*$")


def _is_header(line: str) -> bool:
    return bool(_HEADER_RE.match(line))


def _is_list_item(line: str) -> bool:
    return bool(_LIST_RE.match(line))


def _is_table_row(line: str) -> bool:
    return "|" in line and line.strip() != ""


def _is_table_delim(line: str) -> bool:
    return bool(_TABLE_DELIM_RE.match(line)) and "-" in line


def _strip_headers(text: str) -> str:
    """Remove header lines from separator text, leaving surrounding whitespace."""
    return _HEADER_LINE_RE.sub("", text)


def _sentence_spans(text: str) -> List[tuple[int, int]]:
    """Return (start, end) char offsets of each sentence within ``text``."""
    spans: List[tuple[int, int]] = []
    cursor = 0
    for sentence in nltk.sent_tokenize(text):
        start = text.find(sentence, cursor)
        if start == -1:
            continue
        end = start + len(sentence)
        spans.append((start, end))
        cursor = end
    return spans



# Used for splitting context -> sources and for splitting response -> units

def _line_spans(text: str) -> List[tuple[int, int, str]]:
    """(content_start, content_end, raw_line) per line. content_end excludes the
    trailing newline so it falls into the separator, not the unit."""
    out: List[tuple[int, int, str]] = []
    idx = 0
    for raw in text.splitlines(keepends=True):
        content_end = idx + len(raw.rstrip("\n"))
        out.append((idx, content_end, raw))
        idx += len(raw)
    return out


def _consume_table(lines, i, spans) -> int:
    """If lines[i:] start a real table, append one span and return the next index.
    Otherwise return 0 to signal "not a table"."""
    n = len(lines)
    j = i
    while j < n and _is_table_row(lines[j][2].strip()):
        j += 1
    block = lines[i:j]
    if not any(_is_table_delim(ln[2]) for ln in block):
        return 0
    spans.append((block[0][0], block[-1][1]))
    return j


def _consume_list_item(lines, i, spans) -> int:
    """Append one list-item span (marker line + indented continuations)."""
    n = len(lines)
    start = lines[i][0]
    end = lines[i][1]
    i += 1
    while i < n:
        _, c_end, raw = lines[i]
        stripped = raw.strip()
        if stripped == "" or _is_header(stripped) or _is_list_item(stripped):
            break
        if "|" in stripped:  # start of a table ends the item
            break
        if raw[:1] not in (" ", "\t"):  # non-indented => new block
            break
        end = c_end
        i += 1
    spans.append((start, end))
    return i


def _consume_paragraph(text, lines, i, spans) -> int:
    """Gather consecutive plain-text lines and emit one span per sentence."""
    n = len(lines)
    start = lines[i][0]
    end = lines[i][1]
    i += 1
    while i < n:
        _, c_end, raw = lines[i]
        stripped = raw.strip()
        if (
            stripped == ""
            or _is_header(stripped)
            or _is_list_item(stripped)
            or "|" in stripped
        ):
            break
        end = c_end
        i += 1
    para = text[start:end]
    for s_start, s_end in _sentence_spans(para):
        spans.append((start + s_start, start + s_end))
    return i


def markdown_unit_spans(text: str) -> List[tuple[int, int]]:
    """(start, end) char offsets of every markdown unit in ``text``.

    A unit is a sentence (within prose), a bullet / numbered list item (with its
    indented continuations), or a whole table; headers and blank lines are
    skipped. Shared by the context partitioner (to make sources) and by per-unit
    response attribution (to make target spans), so both sides segment structured
    text identically.
    """
    lines = _line_spans(text)
    n = len(lines)
    spans: List[tuple[int, int]] = []
    i = 0
    while i < n:
        start, end, raw = lines[i]
        stripped = raw.strip()

        if stripped == "" or _is_header(stripped):
            i += 1  # blank lines and headers are not units
            continue

        if _is_table_row(stripped):
            consumed = _consume_table(lines, i, spans)
            if consumed:
                i = consumed
                continue
            # Not a real table -- fall through and treat as plain text.

        if _is_list_item(stripped):
            i = _consume_list_item(lines, i, spans)
            continue

        i = _consume_paragraph(text, lines, i, spans)
    return spans


class MarkdownContextPartitioner(BaseContextPartitioner):
    """Partition markdown context into header-stripped, structure-aware sources."""

    def __init__(self, context: str) -> None:
        super().__init__(context)
        self._parts: Optional[List[str]] = None
        self._separators: Optional[List[str]] = None

    # splitting

    def split_context(self) -> None:
        spans = markdown_unit_spans(self.context)
        context = self.context
        parts: List[str] = []
        separators: List[str] = []
        prev_end = 0
        for start, end in spans:
            separators.append(_strip_headers(context[prev_end:start]))
            parts.append(context[start:end])
            prev_end = end
        self._parts = parts
        self._separators = separators

    # cached views

    @property
    def parts(self) -> List[str]:
        if self._parts is None:
            self.split_context()
        return self._parts  # type: ignore[return-value]

    @property
    def separators(self) -> List[str]:
        if self._separators is None:
            self.split_context()
        return self._separators  # type: ignore[return-value]

    # BaseContextPartitioner API 

    @property
    def num_sources(self) -> int:
        return len(self.parts)

    def get_source(self, index: int) -> str:
        return self.parts[index]

    def get_context(self, mask: Optional[NDArray] = None) -> str:
        if mask is None:
            mask = np.ones(self.num_sources, dtype=bool)
        separators = np.array(self.separators, dtype=object)[mask]
        parts = np.array(self.parts, dtype=object)[mask]
        context = ""
        for i, (separator, part) in enumerate(zip(separators, parts)):
            if i > 0:
                context += separator
            context += part
        return context
