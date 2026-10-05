"""
Diagnostic service — ping, traceroute, and nslookup.

When ``FAKE_DIAGNOSTICS=True`` (default), all functions return deterministic
mocked results without touching the network. This is suitable for development
and demo environments.

When ``FAKE_DIAGNOSTICS=False``, the service runs real system commands
(traceroute, ping, nslookup) via asyncio subprocess.
"""

from __future__ import annotations

import asyncio
import logging
import re

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FAKE diagnostics (deterministic mocks)
# ---------------------------------------------------------------------------

_PRIVATE_IP_RE = re.compile(r"^10\.|^192\.168\.|^172\.(1[6-9]|2[0-9]|3[01])\.")


def _is_private_ip(host: str) -> bool:
    """Return True if *host* looks like an RFC-1918 private IP."""
    return bool(_PRIVATE_IP_RE.match(host))


def _fake_ping(host: str, count: int = 4) -> dict:
    """Generate a fake ping result.

    Hosts in the 10.x.x.x range (or other private IPs) simulate 100% packet
    loss; all other hosts return a realistic successful response.

    Args:
        host: Target IP or hostname.
        count: Number of packets simulated.

    Returns:
        Ping result dict.
    """
    if _is_private_ip(host):
        # Simulate unreachable private IP
        return {
            "host": host,
            "packets_sent": count,
            "packets_received": 0,
            "packet_loss_pct": 100.0,
            "avg_rtt_ms": None,
            "reachable": False,
        }
    return {
        "host": host,
        "packets_sent": count,
        "packets_received": count,
        "packet_loss_pct": 0.0,
        "avg_rtt_ms": 12.4,
        "reachable": True,
    }


def _fake_traceroute(host: str) -> dict:
    """Generate a fake traceroute result with a failure at hop 3.

    Args:
        host: Target IP or hostname.

    Returns:
        Traceroute result dict with ``hops`` list.
    """
    hops = [
        {"hop": 1, "host": "10.0.0.1",     "rtt_ms": 1.2},
        {"hop": 2, "host": "172.16.0.1",   "rtt_ms": 4.8},
        {"hop": 3, "host": "* * *",        "rtt_ms": None},   # <-- failure point
        {"hop": 4, "host": "* * *",        "rtt_ms": None},
        {"hop": 5, "host": "* * *",        "rtt_ms": None},
    ]
    return {
        "host": host,
        "hops": hops,
        "completed": False,
        "error": "Destination unreachable at hop 3 — possible route black-hole or firewall drop",
    }


def _fake_nslookup(host: str) -> dict:
    """Generate plausible fake DNS lookup data.

    Args:
        host: Target IP or hostname.

    Returns:
        NSLookup result dict.
    """
    # If host already looks like an IP, simulate reverse lookup
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return {
            "host": host,
            "addresses": [host],
            "reverse_lookup": f"ptr-{host.replace('.', '-')}.noc.internal",
            "error": None,
        }
    return {
        "host": host,
        "addresses": ["10.20.30.40", "10.20.30.41"],
        "reverse_lookup": f"{host}.noc.internal",
        "error": None,
    }


# ---------------------------------------------------------------------------
# REAL diagnostics via system commands
# ---------------------------------------------------------------------------

async def _run_command(cmd: list[str], timeout: float = 15.0) -> tuple[str, str, int]:
    """Run a shell command asynchronously and return (stdout, stderr, returncode).

    Args:
        cmd: Command as a list of strings (no shell=True for safety).
        timeout: Maximum seconds to wait for the process.

    Returns:
        Tuple of (stdout_str, stderr_str, returncode).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode(), stderr.decode(), proc.returncode or 0
    except asyncio.TimeoutError:
        return "", "Command timed out", -1
    except Exception as exc:
        return "", str(exc), -1


async def _real_ping(host: str, count: int = 4) -> dict:
    """Run the system ``ping`` command.

    Args:
        host: Target IP or hostname.
        count: Number of ICMP packets.

    Returns:
        Structured ping result dict.
    """
    stdout, stderr, code = await _run_command(["ping", "-c", str(count), host])
    # Parse packet loss line: "4 packets transmitted, 4 received, 0% packet loss"
    loss_match = re.search(r"(\d+)% packet loss", stdout)
    rtt_match = re.search(r"min/avg/max.*?=\s*[\d.]+/([\d.]+)/", stdout)
    rcv_match = re.search(r"(\d+) received", stdout)

    loss_pct = float(loss_match.group(1)) if loss_match else 100.0
    avg_rtt = float(rtt_match.group(1)) if rtt_match else None
    received = int(rcv_match.group(1)) if rcv_match else 0

    return {
        "host": host,
        "packets_sent": count,
        "packets_received": received,
        "packet_loss_pct": loss_pct,
        "avg_rtt_ms": avg_rtt,
        "reachable": loss_pct < 100.0,
    }


async def _real_traceroute(host: str) -> dict:
    """Run the system ``traceroute`` command.

    Args:
        host: Target IP or hostname.

    Returns:
        Structured traceroute result dict.
    """
    stdout, stderr, code = await _run_command(["traceroute", "-m", "15", host], timeout=30)
    hops = []
    for line in stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if not parts:
            continue
        try:
            hop_num = int(parts[0])
        except ValueError:
            continue
        hop_host = parts[1] if len(parts) > 1 else "* * *"
        # Look for RTT in ms (e.g., "12.345 ms")
        rtt_match = re.search(r"([\d.]+)\s+ms", line)
        rtt_ms = float(rtt_match.group(1)) if rtt_match else None
        hops.append({"hop": hop_num, "host": hop_host, "rtt_ms": rtt_ms})

    completed = code == 0 and bool(hops) and hops[-1]["rtt_ms"] is not None
    return {
        "host": host,
        "hops": hops,
        "completed": completed,
        "error": stderr.strip() if stderr.strip() else None,
    }


async def _real_nslookup(host: str) -> dict:
    """Run the system ``nslookup`` command.

    Args:
        host: Target IP or hostname.

    Returns:
        Structured nslookup result dict.
    """
    stdout, stderr, code = await _run_command(["nslookup", host], timeout=10)
    addresses = re.findall(r"Address:\s*([\d.a-fA-F:]+)(?!\s*#)", stdout)
    # Remove the server address (first entry is usually the DNS server itself)
    if addresses:
        addresses = addresses[1:]  # skip the DNS server IP

    reverse_match = re.search(r"name\s*=\s*(.+)", stdout, re.IGNORECASE)
    reverse = reverse_match.group(1).strip().rstrip(".") if reverse_match else None

    return {
        "host": host,
        "addresses": list(set(addresses)),
        "reverse_lookup": reverse,
        "error": stderr.strip() if stderr.strip() else None,
    }


# ---------------------------------------------------------------------------
# Public API — dispatch to fake or real based on config
# ---------------------------------------------------------------------------

async def run_ping(host: str, count: int = 4) -> dict:
    """Run a ping diagnostic, fake or real depending on ``FAKE_DIAGNOSTICS``.

    Args:
        host: Target IP or hostname.
        count: Number of ICMP echo requests.

    Returns:
        Ping result dict compatible with ``PingResult`` schema.
    """
    logger.debug("ping host=%s count=%d fake=%s", host, count, settings.FAKE_DIAGNOSTICS)
    if settings.FAKE_DIAGNOSTICS:
        return _fake_ping(host, count)
    return await _real_ping(host, count)


async def run_traceroute(host: str) -> dict:
    """Run a traceroute diagnostic, fake or real depending on ``FAKE_DIAGNOSTICS``.

    Args:
        host: Target IP or hostname.

    Returns:
        Traceroute result dict compatible with ``TracerouteResult`` schema.
    """
    logger.debug("traceroute host=%s fake=%s", host, settings.FAKE_DIAGNOSTICS)
    if settings.FAKE_DIAGNOSTICS:
        return _fake_traceroute(host)
    return await _real_traceroute(host)


async def run_nslookup(host: str) -> dict:
    """Run an nslookup diagnostic, fake or real depending on ``FAKE_DIAGNOSTICS``.

    Args:
        host: Target IP or hostname.

    Returns:
        NSLookup result dict compatible with ``NslookupResult`` schema.
    """
    logger.debug("nslookup host=%s fake=%s", host, settings.FAKE_DIAGNOSTICS)
    if settings.FAKE_DIAGNOSTICS:
        return _fake_nslookup(host)
    return await _real_nslookup(host)


async def run_all_diagnostics(host: str, count: int = 4) -> dict:
    """Run ping, traceroute, and nslookup concurrently for a given host.

    Args:
        host: Target IP or hostname.
        count: Ping packet count.

    Returns:
        Dict with ``ping``, ``traceroute``, ``nslookup`` sub-dicts.
    """
    ping_result, traceroute_result, nslookup_result = await asyncio.gather(
        run_ping(host, count),
        run_traceroute(host),
        run_nslookup(host),
    )
    return {
        "ping": ping_result,
        "traceroute": traceroute_result,
        "nslookup": nslookup_result,
    }
