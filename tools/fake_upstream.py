#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""假的 GPT-SoVITS 上游，只用于测试中继（不需要模型、不需要网络）。

模拟 api_v2.py 的关键行为：
  GET  /control             -> 400 JSON（没带 command）
  GET  /set_gpt_weights     -> 200 {"message":"success"}
  GET  /set_sovits_weights  -> 200 {"message":"success"}
  POST /tts                 -> wav（带 Content-Length）
  GET  /stream              -> 无 Content-Length 的流式 wav（测中继的 chunked 透传）
"""
from __future__ import annotations

import argparse
import io
import math
import struct
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LAST = {"gpt": "", "sovits": ""}


def make_wav(seconds: float = 0.5, rate: int = 32000, freq: float = 440.0) -> bytes:
    frames = int(seconds * rate)
    raw = b"".join(
        struct.pack("<h", int(6000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(frames)
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(raw)
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    def _json(self, obj, status=200):
        body = str(obj).encode() if isinstance(obj, bytes) else __import__("json").dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        if parsed.path == "/control":
            return self._json({"message": "command is required"}, 400)
        if parsed.path == "/set_gpt_weights":
            LAST["gpt"] = (q.get("weights_path") or [""])[0]
            return self._json({"message": "success"})
        if parsed.path == "/set_sovits_weights":
            LAST["sovits"] = (q.get("weights_path") or [""])[0]
            return self._json({"message": "success"})
        if parsed.path == "/stream":
            rate, total = 16000, 32000
            chunks = [b"\x00\x00" * 4000] * (total // 4000)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(b"%X\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            return
        return self._json({"message": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        if urlparse(self.path).path != "/tts":
            return self._json({"message": "not found"}, 404)

        import json
        try:
            req = json.loads(body.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return self._json({"message": "bad json"}, 400)

        missing = [k for k in ("text", "text_lang", "ref_audio_path", "prompt_lang") if not req.get(k)]
        if missing:
            return self._json({"message": "missing " + ",".join(missing)}, 400)

        data = make_wav()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9882)
    args = p.parse_args()
    print(f"[fake-upstream] listen :{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
