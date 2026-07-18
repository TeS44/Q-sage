"""
Local web UI for interactive play (issue #3).

Modes:
  - Hex boards: human, random, QBF (initial / mid-game), QBF-guided Black
  - Certificates: play against a winning-strategy CNF cert
  - Grid problems: list + “does Black win?” via bwnib+QuBi
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from qsage.web.catalog import list_all_problems
from qsage.web import cert_session, hex_session

_REPO = Path(__file__).resolve().parents[2]
_STATIC = Path(__file__).parent / "static"
_SESSIONS: dict[str, dict] = {}


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
        self._send(200 if code == 200 else code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(200, (_STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
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
        if u.path == "/api/problems":
            self._json(200, {"problems": list_all_problems()})
            return
        if u.path == "/api/new":
            qs = parse_qs(u.query)
            path = (qs.get("path") or [None])[0]
            kind = (qs.get("kind") or ["hex"])[0]
            if not path:
                self._json(400, {"error": "path required"})
                return
            try:
                if kind == "certificate":
                    sess = cert_session.new_cert_session(path)
                    _SESSIONS[sess["session"]] = sess
                    self._json(200, cert_session.public_cert(sess))
                elif kind == "grid":
                    # Grid: store path/domain for solve-only session (no cell play yet)
                    domain = (qs.get("domain") or [None])[0]
                    import uuid as _uuid

                    sid = _uuid.uuid4().hex
                    sess = {
                        "session": sid,
                        "kind": "grid",
                        "path": path,
                        "domain": domain,
                        "cells": {},
                        "to_move": "—",
                        "finished": False,
                        "winner": None,
                        "depth_bound": 0,
                        "moves_played": 0,
                        "message": "Grid instance — use “QBF: Black wins?” to solve (bwnib).",
                    }
                    _SESSIONS[sid] = sess
                    self._json(200, sess)
                else:
                    sess = hex_session.new_hex_session(path)
                    _SESSIONS[sess["session"]] = sess
                    self._json(200, hex_session.public_hex(sess))
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
                    # white user move
                    pub = cert_session.white_move(sess, body["position"])
                    self._json(200, pub)
                    return
                if sess.get("kind") != "hex":
                    self._json(400, {"error": "moves only for hex/certificate"})
                    return
                pos = body["position"]
                mode = body.get("opponent") or "random"  # random | none | qbf
                hex_session.apply_move(sess, pos)
                last = None
                if not sess["finished"] and sess["to_move"] == "B":
                    if mode == "random":
                        last = hex_session.random_move(sess, "B")
                    elif mode == "qbf":
                        last = hex_session.ai_qbf_black_move(sess)
                pub = hex_session.public_hex(sess)
                if last:
                    pub["last_ai"] = sess.get("last_ai")
                self._json(200, pub)
                return

            if u.path == "/api/ai":
                if not sess:
                    self._json(400, {"error": "unknown session"})
                    return
                mode = body.get("mode") or "random"
                color = body.get("color") or sess.get("to_move")
                if sess.get("kind") == "certificate":
                    if mode in ("strategy", "random", "qbf"):
                        pub = cert_session.strategy_black_move(sess)
                        self._json(200, pub)
                        return
                if sess.get("kind") == "hex":
                    if mode == "random":
                        hex_session.random_move(sess, color)
                    elif mode == "qbf" and color == "B":
                        hex_session.ai_qbf_black_move(sess)
                    else:
                        hex_session.random_move(sess, color)
                    self._json(200, hex_session.public_hex(sess))
                    return
                self._json(400, {"error": "ai not available"})
                return

            if u.path == "/api/undo":
                if not sess or sess.get("kind") != "hex":
                    self._json(400, {"error": "undo only for hex"})
                    return
                hex_session.undo(sess)
                # undo twice if last was AI black after white
                if body.get("undo_ai") and sess["history"]:
                    hex_session.undo(sess)
                self._json(200, hex_session.public_hex(sess))
                return

            if u.path == "/api/solve":
                if not sess:
                    self._json(400, {"error": "unknown session"})
                    return
                mid = bool(body.get("midgame"))
                enc = body.get("encoding") or "pg"
                if sess.get("kind") == "hex":
                    self._json(200, hex_session.solve_qbf(sess, midgame=mid, encoding=enc))
                    return
                if sess.get("kind") == "grid":
                    from qsage.encode.bwnib import encode_bwnib
                    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

                    if not qubi_available():
                        self._json(200, {"status": "ERROR", "detail": "QuBi missing"})
                        return
                    domain = _REPO / (sess.get("domain") or "")
                    problem = _REPO / sess["path"]
                    qcir = encode_bwnib(domain, problem)
                    res = solve_qcir_qubi(qcir, timeout=int(body.get("timeout") or 120))
                    self._json(
                        200,
                        {
                            "status": res.status.value,
                            "seconds": res.seconds,
                            "detail": "bwnib on grid instance",
                            "meaning": (
                                "Black winning strategy (SAT)"
                                if res.status.value == "SAT"
                                else "No Black win in bound (UNSAT)"
                                if res.status.value == "UNSAT"
                                else res.message
                            ),
                        },
                    )
                    return
                self._json(400, {"error": "solve not supported for this kind"})
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
