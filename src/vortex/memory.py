"""Memory figures: the displayed RAM usage with its source named.

Owns the whole memory-figure surface: the vm_stat parse (primary source),
the named-source selection, the public wrappers the status API reports, and
the psutil total. Nothing here is blended: the figure and its source label
always travel together.
"""

from __future__ import annotations

import re
import subprocess

import psutil  # type: ignore[import-untyped]


def _activity_monitor_used_gb() -> float:
    try:
        out = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return 0.0
    # vm_stat names its own page size in the header (16384 on Apple Silicon,
    # 4096 on Intel). The page counts below are in units of THAT size, so parse
    # it from the output instead of hardcoding — a fixed 16384 scales the whole
    # figure 4x wrong on an Intel host. A missing header is a malformed vm_stat:
    # report 0.0 (degraded source), never guess a page size.
    page_match = re.search(r"page size of (\d+) bytes", out)
    if page_match is None:
        return 0.0
    page_size = int(page_match.group(1))
    pages = {}
    for line in out.splitlines():
        m = re.match(r"\s*([\w ]+):\s+(\d+)\.", line)
        if m:
            pages[m.group(1).strip()] = int(m.group(2))
    keys = [
        "Pages active",
        "Pages inactive",
        "Pages speculative",
        "Pages wired down",
        "Pages occupied by compressor",
    ]
    if any(k not in pages for k in keys):
        return 0.0
    return sum(pages[k] for k in keys) * page_size / (1024**3)


def _ram_used() -> tuple[float, str]:
    """The displayed memory figure with its source named.

    One source of truth (CEO ruling, tasks/CURRENT.md 2026-08-17): the
    Activity Monitor figure — vm_stat's wired+compressor+active+inactive+
    speculative pages — is what the UI reports, because that matches what
    `top`/Activity Monitor show the operator. psutil-used (~15GB lower on
    macOS: it excludes inactive/compressor/wired overheads) remains ONLY as
    an explicitly-labeled degraded source for hosts without vm_stat (Linux);
    it is never silently blended into the same number.
    """
    vm_stat_gb = _activity_monitor_used_gb()
    if vm_stat_gb > 0.0:
        return vm_stat_gb, "vm_stat"
    return psutil.virtual_memory().used / (1024**3), "psutil"


def estimate_ram_used_gb() -> float:
    return _ram_used()[0]


def ram_used_source() -> str:
    return _ram_used()[1]


def estimate_ram_total_gb() -> float:
    return psutil.virtual_memory().total / (1024**3)
