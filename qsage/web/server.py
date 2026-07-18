"""Minimal localhost UI: Hex occupy play + optional QuBi check."""

from __future__ import annotations

import json
import random
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from qsage.parse.positional import parse_pg

_REPO = Path(__file__).resolve().parents[2]
_STATIC = Path(__file__).parent / "static"
_SESSIONS: dict[str, dict] = {}


def _list_problems() -> list[dict]:
    out = []
    for p in sorted((_REPO / "Benchmarks" / "B-Hex").glob("*.pg")):
        # prefer small boards in the list first
        out.append({"path": str(p.relative_to(_REPO)), "label": p.name})
    return out


def _new_session(rel_path: str) -> dict:
    path = (_REPO / rel_path).resolve()
    if not str(path).startswith(str(_REPO.resolve())):
        raise ValueError("path outside repo")
    game = parse_pg(path)
    cells = {pos: "open" for pos in game.positions}
    for pos in game.black_initials:
        cells[pos] = "B"
    for pos in game.white_initials:
        cells[pos] = "W"
    sid = uuid.uuid4().hex
    sess = {
        "session": sid,
        "path": rel_path,
        "positions": list(game.positions),
        "neighbours": {k: list(v) for k, v in game.neighbours.items()},
        "cells": cells,
        "history": [],
        "to_move": "B",  # Black first in maker-breaker Hex
        "finished": False,
        "winner": None,
        "hex": True,
        "depth_bound": game.depth,
        "moves_played": 0,
        "last_black": None,
    }
    _SESSIONS[sid] = sess
    return _public(sess)


def _public(sess: dict) -> dict:
    return {
        "session": sess["session"],
        "path": sess["path"],
        "cells": dict(sess["cells"]),
        "to_move": sess["to_move"],
        "finished": sess["finished"],
        "winner": sess["winner"],
        "hex": sess["hex"],
        "depth_bound": sess["depth_bound"],
        "moves_played": sess["moves_played"],
        "last_black": sess.get("last_black"),
    }


def _open_cells(sess: dict) -> list[str]:
    return [p for p, v in sess["cells"].items() if v == "open"]


def _apply_move(sess: dict, pos: str, color: str) -> None:
    if sess["finished"]:
        raise ValueError("game finished")
    if pos not in sess["cells"] or sess["cells"][pos] != "open":
        raise ValueError(f"illegal move {pos}")
    if color != sess["to_move"]:
        raise ValueError(f"not {color}'s turn")
    sess["cells"][pos] = color
    sess["history"].append((pos, color))
    sess["moves_played"] += 1
    sess["to_move"] = "W" if color == "B" else "B"
    if sess["moves_played"] >= sess["depth_bound"]:
        sess["finished"] = True
    if not _open_cells(sess):
        sess["finished"] = True


def _random_black(sess: dict) -> str | None:
    opens = _open_cells(sess)
    if not opens or sess["finished"] or sess["to_move"] != "B":
        return None
    pos = random.choice(opens)
    _apply_move(sess, pos, "B")
    sess["last_black"] = pos
    return pos


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        # quieter default
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        data = json.dumps(obj).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            html = (_STATIC / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
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
            self._json(200, {"problems": _list_problems()})
            return
        if u.path == "/api/new":
            qs = parse_qs(u.query)
            path = (qs.get("path") or [None])[0]
            if not path:
                self._json(400, {"error": "path required"})
                return
            try:
                self._json(200, _new_session(path))
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
        if u.path == "/api/move":
            sess = _SESSIONS.get(body.get("session") or "")
            if not sess:
                self._json(400, {"error": "unknown session"})
                return
            try:
                # Human plays White in UI by default when auto_black is on
                # after their move; if it's Black's turn and auto is off, allow B.
                pos = body["position"]
                color = sess["to_move"]
                _apply_move(sess, pos, color)
                last_b = None
                if (
                    body.get("auto_black")
                    and not sess["finished"]
                    and sess["to_move"] == "B"
                ):
                    last_b = _random_black(sess)
                pub = _public(sess)
                pub["last_black"] = last_b
                self._json(200, pub)
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if u.path == "/api/undo":
            sess = _SESSIONS.get(body.get("session") or "")
            if not sess or not sess["history"]:
                self._json(400, {"error": "nothing to undo"})
                return
            pos, color = sess["history"].pop()
            sess["cells"][pos] = "open"
            sess["moves_played"] -= 1
            sess["to_move"] = color
            sess["finished"] = False
            sess["winner"] = None
            sess["last_black"] = None
            self._json(200, _public(sess))
            return
        if u.path == "/api/solve":
            sess = _SESSIONS.get(body.get("session") or "")
            if not sess:
                self._json(400, {"error": "unknown session"})
                return
            # Re-solve original problem encoding (full depth), not mid-game rewrite —
            # honest "does Black have a win from the *initial* puzzle?"
            try:
                from qsage.encode.positional import encode_positional
                from qsage.solve.qubi import solve_qcir_qubi

                qcir = encode_positional(_REPO / sess["path"], "pg")
                res = solve_qcir_qubi(qcir, timeout=60)
                self._json(
                    200,
                    {
                        "status": res.status.value,
                        "seconds": res.seconds,
                        "detail": "pg encoding of original puzzle (not mid-game)",
                        "message": res.message,
                    },
                )
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
