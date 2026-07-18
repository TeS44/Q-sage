"""
Local web UI for interactive play (issue #3).

- Pick **domain** then **instance** (buttons)
- Run with **QBF**, **Certificate**, or **Hybrid** (partial cert openings)
"""

from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from qsage.web import cert_session, hex_session
from qsage.web.catalog import list_all_problems
from qsage.web.partial_certs import has_partial, list_partial_certs, load_partial

_REPO = Path(__file__).resolve().parents[2]
_STATIC = Path(__file__).parent / "static"
_SESSIONS: dict[str, dict] = {}


def _domains() -> list[dict]:
    """Unique domains/groups with counts and play modes."""
    probs = list_all_problems()
    groups: dict[str, dict] = {}
    for p in probs:
        g = p["group"]
        if g not in groups:
            kind = p["kind"]
            modes = []
            if kind == "hex":
                modes = ["qbf", "hybrid"]
            elif kind == "certificate":
                modes = ["certificate"]
            elif kind == "grid":
                modes = ["qbf"]
            groups[g] = {
                "id": g,
                "label": g,
                "kind": kind,
                "count": 0,
                "modes": modes,
            }
        groups[g]["count"] += 1
    # stable order
    order = []
    for key in (
        "Hex (B-Hex)",
        "Hex (GDDL)",
        "Certificates (strategy)",
    ):
        if key in groups:
            order.append(groups.pop(key))
    for g in sorted(groups.values(), key=lambda x: x["label"]):
        order.append(g)
    return order


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(
            code,
            json.dumps(obj).encode(),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(
                200,
                (_STATIC / "index.html").read_bytes(),
                "text/html; charset=utf-8",
            )
            return
        if u.path.startswith("/static/"):
            name = u.path[len("/static/") :]
            f = (_STATIC / name).resolve()
            if not str(f).startswith(str(_STATIC.resolve())) or not f.is_file():
                self._json(404, {"error": "not found"})
                return
            ctype = (
                "application/javascript"
                if f.suffix == ".js"
                else "text/css"
                if f.suffix == ".css"
                else "application/octet-stream"
            )
            self._send(200, f.read_bytes(), ctype)
            return

        if u.path == "/api/domains":
            self._json(200, {"domains": _domains()})
            return

        if u.path == "/api/problems":
            qs = parse_qs(u.query)
            domain = (qs.get("domain") or [None])[0]
            all_flag = (qs.get("all") or ["0"])[0] in ("1", "true", "yes")
            probs = list_all_problems(qbf_only=not all_flag)
            if domain:
                probs = [p for p in probs if p["group"] == domain]
            for p in probs:
                p["has_partial"] = False  # partial certs deferred
            self._json(
                200,
                {
                    "problems": probs,
                    "qbf_only": not all_flag,
                    "note": "QuBi hard-killed after timeout (default 3s); see playable_qbf.json",
                },
            )
            return

        if u.path == "/api/partials":
            self._json(200, {"partials": list_partial_certs()})
            return

        if u.path == "/api/new":
            qs = parse_qs(u.query)
            path = (qs.get("path") or [None])[0]
            kind = (qs.get("kind") or ["hex"])[0]
            mode = (qs.get("mode") or ["qbf"])[0]  # qbf | certificate | hybrid
            if not path:
                self._json(400, {"error": "path required"})
                return
            try:
                if kind == "certificate" or mode == "certificate":
                    sess = cert_session.new_cert_session(path)
                    sess["play_mode"] = "certificate"
                    _SESSIONS[sess["session"]] = sess
                    pub = cert_session.public_cert(sess)
                    pub["play_mode"] = "certificate"
                    self._json(200, pub)
                    return
                if kind == "grid":
                    domain = (qs.get("domain_file") or qs.get("domain") or [None])[0]
                    # catalog uses "domain" key for domain.ig path
                    sid = uuid.uuid4().hex
                    # find domain from catalog if missing
                    if not domain:
                        for p in list_all_problems():
                            if p["path"] == path:
                                domain = p.get("domain")
                                break
                    sess = {
                        "session": sid,
                        "kind": "grid",
                        "path": path,
                        "domain": domain,
                        "play_mode": "qbf",
                        "cells": {},
                        "to_move": "—",
                        "finished": False,
                        "winner": None,
                        "depth_bound": 0,
                        "moves_played": 0,
                        "message": "Grid — use QBF to check if Black wins (bwnib).",
                    }
                    _SESSIONS[sid] = sess
                    self._json(200, sess)
                    return

                # hex — vs engine: you are White, opponent Black
                sess = hex_session.new_hex_session(path)
                sess["play_mode"] = mode if mode in ("qbf", "hybrid", "random", "none") else "qbf"
                sess["human_color"] = "W"
                sess["ai_color"] = "B"
                if sess["play_mode"] == "none":
                    sess["human_color"] = "B"  # first to move; manual both
                    sess["ai_color"] = "W"
                    sess["message"] = "Manual mode: you play both colours."
                elif sess["play_mode"] == "hybrid":
                    book = load_partial(path)
                    n = len((book or {}).get("layers") or [])
                    sess["message"] = (
                        f"You are White · opponent Black (hybrid). "
                        f"Partial book: {n} plies."
                        if book
                        else "You are White · opponent Black (hybrid → QBF)."
                    )
                elif sess["play_mode"] == "qbf":
                    sess["message"] = "You are White · opponent Black (QBF / QuBi)."
                elif sess["play_mode"] == "random":
                    sess["message"] = "You are White · opponent Black (random)."
                _SESSIONS[sess["session"]] = sess
                # If this instance has Black to move first, QBF/AI opens as Black
                # server-side so the human never paints the opening stone.
                t_ai = 3.0
                if (
                    sess["play_mode"] in ("qbf", "hybrid", "random")
                    and sess.get("to_move") == sess.get("ai_color", "B")
                ):
                    try:
                        hex_session.maybe_play_ai(sess, timeout=t_ai)
                    except Exception:
                        pass  # leave needs_ai_move for client retry
                pub = hex_session.public_hex(sess)
                pub["has_partial"] = has_partial(path)
                self._json(200, pub)
            except Exception as e:
                self._json(400, {"error": str(e)})
            return

        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "bad json"})
            return
        u = urlparse(self.path)
        sess = _SESSIONS.get(body.get("session") or "")

        try:
            if u.path == "/api/move":
                if not sess:
                    self._json(400, {"error": "unknown session"})
                    return
                if sess.get("kind") == "certificate":
                    pub = cert_session.white_move(sess, body["position"])
                    pub["play_mode"] = "certificate"
                    self._json(200, pub)
                    return
                if sess.get("kind") != "hex":
                    self._json(400, {"error": "board moves only for hex/certificate"})
                    return
                pos = body["position"]
                mode = body.get("opponent") or sess.get("play_mode") or "qbf"
                sess["play_mode"] = mode if mode in ("qbf", "hybrid", "random", "none") else sess.get("play_mode") or "qbf"
                human = sess.get("human_color") or "W"
                ai = sess.get("ai_color") or "B"
                t_ai = float(body.get("timeout") or 2.0)

                # If AI still to move (e.g. opening failed), play AI first
                if (
                    sess["play_mode"] in ("qbf", "hybrid", "random")
                    and sess["to_move"] == ai
                    and not sess["finished"]
                ):
                    hex_session.maybe_play_ai(sess, timeout=t_ai)
                    if sess["to_move"] != human and not sess["finished"]:
                        self._json(
                            400,
                            {
                                "error": (
                                    "Still opponent's turn (Black). "
                                    "Wait for AI or click “AI / strategy move”."
                                ),
                                "state": hex_session.public_hex(sess),
                            },
                        )
                        return

                # Human places only White (forced in apply_move)
                hex_session.apply_move(sess, pos, color=human, as_human=True)
                # Black replies
                if (
                    not sess["finished"]
                    and sess["to_move"] == ai
                    and sess["play_mode"] in ("hybrid", "qbf", "random")
                ):
                    hex_session.maybe_play_ai(sess, timeout=t_ai)
                self._json(200, hex_session.public_hex(sess))
                return

            if u.path == "/api/ai":
                if not sess:
                    self._json(400, {"error": "unknown session"})
                    return
                mode = body.get("mode") or sess.get("play_mode") or "qbf"
                t_ai = float(body.get("timeout") or 2.0)
                if sess.get("kind") == "certificate":
                    pub = cert_session.strategy_black_move(sess)
                    pub["play_mode"] = "certificate"
                    self._json(200, pub)
                    return
                if sess.get("kind") == "hex":
                    ai = sess.get("ai_color") or "B"
                    if sess["to_move"] != ai and mode != "none":
                        # still allow explicit AI button only on AI's turn
                        self._json(
                            400,
                            {
                                "error": (
                                    f"AI is "
                                    f"{'Black' if ai == 'B' else 'White'}; "
                                    f"it is not their turn"
                                )
                            },
                        )
                        return
                    if mode in ("hybrid", "strategy"):
                        hex_session.ai_hybrid_black_move(sess, qbf_timeout=t_ai)
                    elif mode == "qbf":
                        hex_session.ai_qbf_black_move(sess, timeout=t_ai)
                    else:
                        hex_session.random_move(sess, ai)
                    self._json(200, hex_session.public_hex(sess))
                    return
                self._json(400, {"error": "ai not available"})
                return

            if u.path == "/api/undo":
                if not sess or sess.get("kind") != "hex":
                    self._json(400, {"error": "undo only for hex"})
                    return
                hex_session.undo(sess)
                if body.get("undo_ai") and sess["history"]:
                    hex_session.undo(sess)
                pub = hex_session.public_hex(sess)
                pub["play_mode"] = sess.get("play_mode")
                self._json(200, pub)
                return

            if u.path == "/api/solve":
                if not sess:
                    self._json(400, {"error": "unknown session"})
                    return
                mid = bool(body.get("midgame"))
                enc = body.get("encoding") or "pg"
                # Hard cap for interactive UI (QuBi has no internal timer)
                timeout = float(body.get("timeout") or 3.0)
                timeout = max(0.5, min(timeout, 30.0))
                if sess.get("kind") == "hex":
                    self._json(
                        200,
                        hex_session.solve_qbf(
                            sess, midgame=mid, encoding=enc, timeout=timeout
                        ),
                    )
                    return
                if sess.get("kind") == "grid":
                    from qsage.encode.bwnib import encode_bwnib
                    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

                    if not qubi_available():
                        self._json(
                            200,
                            {"status": "ERROR", "detail": "QuBi missing"},
                        )
                        return
                    domain = _REPO / (sess.get("domain") or "")
                    problem = _REPO / sess["path"]
                    qcir = encode_bwnib(domain, problem)
                    res = solve_qcir_qubi(qcir, timeout=timeout)
                    self._json(
                        200,
                        {
                            "status": res.status.value,
                            "seconds": res.seconds,
                            "detail": "bwnib on grid instance",
                            "timeout": timeout,
                            "meaning": (
                                "Black winning strategy (SAT)"
                                if res.status.value == "SAT"
                                else "No Black win in bound (UNSAT)"
                                if res.status.value == "UNSAT"
                                else f"No answer within {timeout}s"
                                if res.status.value == "TIMEOUT"
                                else res.message
                            ),
                        },
                    )
                    return
                self._json(400, {"error": "solve not supported"})
                return

            self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(400, {"error": str(e)})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Q-sage play UI  http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
