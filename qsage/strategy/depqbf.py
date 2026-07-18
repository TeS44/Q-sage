"""
DepQBF-class tools for partial assignment and certificate generation.

Why this module exists
----------------------
Full winning-strategy certificates are expensive. DepQBF-like solvers make
*partial* certificates and *per-layer* responses cheap:

  - DepQBF ``--qdo`` / QuAbs ``--partial-assignment`` → outermost response
    under assumptions (hybrid interactive tail).
  - Pedant ``--cnf`` → CNF strategy certificate (common in this repo).
  - DepQBF ``--trace`` + qrpcert → AIGER certificate (optional install).

Partial certs + hybrid play (cert for first n layers, solver for the rest)
are the scalable path; see docs/CERTIFICATES.md.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SQVAL = _REPO / "third_party" / "SQval"
_PEDANT = _REPO / "solvers" / "pedant-solver" / "pedant"
_DEPQBF_CERT_DIR = _REPO / "solvers" / "depqbf_cert"


@dataclass
class PartialAssignmentResult:
    """One DepQBF/QuAbs call: SAT/UNSAT plus outermost assignment literals."""

    sat: bool | None
    assignment: list[int] = field(default_factory=list)
    raw: str = ""
    backend: str = ""


@dataclass
class CertGenResult:
    ok: bool
    cert_path: Path | None
    sat: bool | None
    message: str
    raw: str = ""


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def _needs_linux_elf() -> bool:
    return sys.platform != "linux"


def pedant_available() -> bool:
    return _PEDANT.is_file()


def depqbf_sqval_available() -> bool:
    return (_SQVAL / "solvers" / "depqbf" / "depqbf").is_file()


def qrpcert_available() -> bool:
    return (_DEPQBF_CERT_DIR / "qrpcert").is_file() and (
        _DEPQBF_CERT_DIR / "depqbf"
    ).is_file()


def generate_certificate_pedant(
    qdimacs: str | Path,
    out: str | Path,
    *,
    timeout: int = 300,
) -> CertGenResult:
    """
    Generate a CNF strategy certificate with Pedant.

    Command (Linux / Docker)::

        pedant instance.qdimacs --cnf out.cnf
    """
    qdimacs = Path(qdimacs).resolve()
    out = Path(out).resolve()
    if not qdimacs.is_file():
        return CertGenResult(False, None, None, f"missing qdimacs: {qdimacs}")
    if not pedant_available():
        return CertGenResult(
            False,
            None,
            None,
            f"Pedant not found at {_PEDANT}",
        )
    out.parent.mkdir(parents=True, exist_ok=True)

    if _needs_linux_elf() and _docker_ok():
        work = out.parent
        # Prefer a single mount of repo if qdimacs lives under repo
        try:
            rel_in = qdimacs.relative_to(_REPO)
            rel_out = out.relative_to(_REPO)
            inner = (
                "export DEBIAN_FRONTEND=noninteractive; "
                "apt-get update -qq >/dev/null 2>&1; "
                "apt-get install -y -qq libgomp1 >/dev/null 2>&1 || true; "
                f"chmod +x /work/solvers/pedant-solver/pedant; "
                f"/work/solvers/pedant-solver/pedant /work/{rel_in} "
                f"--cnf /work/{rel_out}; "
                f"echo PEDANT_EXIT:$? "
            )
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "-v",
                    f"{_REPO}:/work",
                    "-w",
                    "/work",
                    "ubuntu:22.04",
                    "bash",
                    "-c",
                    inner,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 60,
            )
        except ValueError:
            # Files outside repo: mount dirs separately
            inner = (
                "chmod +x /bin_pedant/pedant; "
                f"/bin_pedant/pedant /in/{qdimacs.name} --cnf /out/{out.name}"
            )
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "-v",
                    f"{qdimacs.parent}:/in:ro",
                    "-v",
                    f"{work}:/out",
                    "-v",
                    f"{_PEDANT.parent}:/bin_pedant:ro",
                    "ubuntu:22.04",
                    "bash",
                    "-c",
                    inner,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 60,
            )
        raw = (proc.stdout or "") + (proc.stderr or "")
    elif _needs_linux_elf():
        return CertGenResult(
            False,
            None,
            None,
            "Pedant is a Linux binary; install Docker or run on Linux/WSL",
        )
    else:
        proc = subprocess.run(
            [str(_PEDANT), str(qdimacs), "--cnf", str(out)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw = (proc.stdout or "") + (proc.stderr or "")

    low = raw.lower()
    sat: bool | None = None
    if "unsatisfiable" in low:
        sat = False
    elif "satisfiable" in low:
        sat = True

    if out.is_file() and out.stat().st_size > 0:
        return CertGenResult(True, out, sat, f"wrote certificate {out}", raw)
    return CertGenResult(
        False,
        None,
        sat,
        "Pedant finished but certificate file missing/empty "
        f"(sat={sat}). Raw tail:\n" + "\n".join(raw.strip().splitlines()[-12:]),
        raw,
    )


def generate_certificate_depqbf_qrp(
    qdimacs: str | Path,
    out: str | Path,
    *,
    timeout: int = 300,
) -> CertGenResult:
    """
    Full AIGER via DepQBF ``--trace`` + qrpcert (optional binaries).

    Expects ``solvers/depqbf_cert/{depqbf,qrpcert}``.
    """
    qdimacs = Path(qdimacs).resolve()
    out = Path(out).resolve()
    if not qrpcert_available():
        return CertGenResult(
            False,
            None,
            None,
            "DepQBF+qrpcert not installed under solvers/depqbf_cert/. "
            "Use `qsage cert generate` with Pedant, or install depqbf_cert "
            "(see docs/CERTIFICATES.md).",
        )
    if not qdimacs.is_file():
        return CertGenResult(False, None, None, f"missing qdimacs: {qdimacs}")

    work = _REPO / "intermediate_files"
    work.mkdir(parents=True, exist_ok=True)
    trace = work / "depqbf_qrp_trace.qrp"
    depqbf = _DEPQBF_CERT_DIR / "depqbf"
    qrpcert = _DEPQBF_CERT_DIR / "qrpcert"

    def _run_local() -> subprocess.CompletedProcess[str]:
        with open(trace, "w", encoding="utf-8") as tf:
            p1 = subprocess.run(
                [str(depqbf), "--trace", str(qdimacs)],
                stdout=tf,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
        p2 = subprocess.run(
            f"{qrpcert} --aiger-ascii --simplify {trace} > {out}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw = (p1.stderr or "") + (p2.stdout or "") + (p2.stderr or "")
        return subprocess.CompletedProcess(
            args=[], returncode=p2.returncode, stdout=raw, stderr=""
        )

    if _needs_linux_elf() and not _docker_ok():
        return CertGenResult(
            False,
            None,
            None,
            "depqbf_cert binaries are Linux ELF; need Docker or Linux/WSL",
        )

    if _needs_linux_elf() and _docker_ok():
        try:
            rel_q = qdimacs.relative_to(_REPO)
            rel_out = out.relative_to(_REPO)
        except ValueError:
            return CertGenResult(
                False,
                None,
                None,
                "for Docker, qdimacs and --out must live under the repo root",
            )
        inner = (
            "chmod +x solvers/depqbf_cert/depqbf solvers/depqbf_cert/qrpcert; "
            f"./solvers/depqbf_cert/depqbf --trace /work/{rel_q} "
            f"> intermediate_files/depqbf_qrp_trace.qrp; "
            "./solvers/depqbf_cert/qrpcert --aiger-ascii --simplify "
            f"intermediate_files/depqbf_qrp_trace.qrp > /work/{rel_out}"
        )
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "-v",
                f"{_REPO}:/work",
                "-w",
                "/work",
                "ubuntu:22.04",
                "bash",
                "-c",
                inner,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 60,
        )
        raw = (proc.stdout or "") + (proc.stderr or "")
    else:
        proc = _run_local()
        raw = proc.stdout or ""

    sat: bool | None = None
    if trace.is_file():
        t = trace.read_text(encoding="utf-8", errors="ignore")
        if "r SAT" in t:
            sat = True
        elif "r UNSAT" in t:
            sat = False

    if out.is_file() and out.stat().st_size > 0:
        return CertGenResult(True, out, sat, f"wrote AIGER certificate {out}", raw)
    return CertGenResult(
        False,
        out if out.is_file() else None,
        sat,
        "DepQBF+qrpcert did not produce a non-empty certificate",
        raw,
    )


def run_depqbf_partial(
    qdimacs: str | Path,
    *,
    timeout: int = 120,
) -> PartialAssignmentResult:
    """
    Run DepQBF with ``--qdo`` for a partial (outermost) assignment.

    Uses SQval's bundled DepQBF; Docker on non-Linux.
    """
    qdimacs = Path(qdimacs).resolve()
    if not depqbf_sqval_available():
        return PartialAssignmentResult(
            None,
            [],
            "SQval DepQBF missing; run bash scripts/setup_sqval.sh",
            "depqbf",
        )
    depqbf = _SQVAL / "solvers" / "depqbf" / "depqbf"

    if _needs_linux_elf() and _docker_ok():
        try:
            rel = qdimacs.relative_to(_SQVAL)
            q_in_container = f"/work/{rel}"
            volume = f"{_SQVAL}:/work"
            workdir = "/work"
        except ValueError:
            try:
                rel = qdimacs.relative_to(_REPO)
                q_in_container = f"/repo/{rel}"
                volume = f"{_REPO}:/repo"
                workdir = "/repo"
                depqbf_in = "/repo/third_party/SQval/solvers/depqbf/depqbf"
            except ValueError:
                return PartialAssignmentResult(
                    None,
                    [],
                    "qdimacs must be under the repo for Docker DepQBF",
                    "depqbf",
                )
            inner = (
                f"chmod +x {depqbf_in}; "
                f"{depqbf_in} --qdo --no-dynamic-nenofex {q_in_container}"
            )
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform",
                    "linux/amd64",
                    "-v",
                    volume,
                    "-w",
                    workdir,
                    "ubuntu:22.04",
                    "bash",
                    "-c",
                    inner,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 30,
            )
            return _parse_depqbf_qdo(proc.stdout + proc.stderr)
        inner = (
            "chmod +x solvers/depqbf/depqbf; "
            f"./solvers/depqbf/depqbf --qdo --no-dynamic-nenofex {q_in_container}"
        )
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "-v",
                volume,
                "-w",
                workdir,
                "ubuntu:22.04",
                "bash",
                "-c",
                inner,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        return _parse_depqbf_qdo(proc.stdout + proc.stderr)

    if _needs_linux_elf():
        return PartialAssignmentResult(
            None,
            [],
            "DepQBF is Linux ELF; install Docker or use WSL",
            "depqbf",
        )

    proc = subprocess.run(
        [str(depqbf), "--qdo", "--no-dynamic-nenofex", str(qdimacs)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return _parse_depqbf_qdo((proc.stdout or "") + (proc.stderr or ""))


def _parse_depqbf_qdo(raw: str) -> PartialAssignmentResult:
    assignment: list[int] = []
    sat: bool | None = None
    for line in raw.splitlines():
        if "s cnf 0" in line:
            sat = False
        elif "s cnf 1" in line:
            sat = True
        if line.startswith("V ") or (line.startswith("V") and " " in line):
            parts = line.split()
            # formats: "V lit 0" or "V lit"
            for p in parts[1:]:
                if p == "0":
                    break
                try:
                    assignment.append(int(p))
                except ValueError:
                    continue
    return PartialAssignmentResult(sat, assignment, raw, "depqbf")
