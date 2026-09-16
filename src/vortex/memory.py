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
    # Working-set only: active + wired + compressor. This is the figure
    # testchat's status surface reports and the one macOS Activity Monitor's
    # "Memory Used" tracks — it excludes inactive + speculative, which are
    # reclaimable file cache and inflate the number by tens of GB without
    # representing memory a new model load must contend for. Supersedes the
    # 2026-08-17 ruling that summed inactive+speculative too (parity with
    # testchat, CEO 2026-09-15).
    keys = [
        "Pages active",
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


def model_rss_gb(pid: int | None) -> float:
    """Resident set size of a loaded model's process, in GB.

    The live per-model footprint the dashboard shows beside each loaded model
    (testchat parity). 0.0 when the pid is unknown or the process is gone —
    a missing figure never masquerades as a real one.
    """
    if pid is None:
        return 0.0
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return int(out.stdout.strip()) / 1024**2
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0.0


def loadable_gb() -> float:
    """GB still available for loading another model (testchat parity).

    Reclaimable memory (free + speculative + purgeable + file-backed) bounded
    by the GPU wired limit headroom (iogpu.wired_limit_mb, else 75% of total),
    minus a 4 GB safety buffer. 0.0 on any failure — the operator sees no
    figure rather than a wrong one.
    """
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        total_gb = int(out.stdout.strip()) / 1024**3

        out = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=2
        )
        page_size = 16384
        pages: dict[str, int] = {}
        for line in out.stdout.splitlines():
            if "page size of" in line:
                page_size = int(line.split("page size of")[1].split()[0])
                continue
            for key in (
                "Pages free:",
                "Pages speculative:",
                "Pages purgeable:",
                "File-backed pages:",
                "Pages wired down:",
            ):
                if line.startswith(key):
                    pages[key] = int(line.split(":")[1].strip().rstrip("."))

        free = pages.get("Pages free:", 0)
        speculative = pages.get("Pages speculative:", 0)
        purgeable = pages.get("Pages purgeable:", 0)
        file_backed = pages.get("File-backed pages:", 0)
        wired_down = pages.get("Pages wired down:", 0)

        reclaimable_gb = (
            (free + speculative + purgeable + file_backed) * page_size / 1024**3
        )
        wired_gb = wired_down * page_size / 1024**3

        try:
            out = subprocess.run(
                ["sysctl", "-n", "iogpu.wired_limit_mb"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            limit_mb = int(out.stdout.strip())
            cap_gb = limit_mb / 1024 if limit_mb > 0 else 0.75 * total_gb
        except (subprocess.SubprocessError, OSError, ValueError):
            cap_gb = 0.75 * total_gb

        return max(0.0, min(reclaimable_gb, cap_gb - wired_gb) - 4.0)
    except (subprocess.SubprocessError, OSError, ValueError):
        return 0.0
