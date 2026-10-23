#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPT-SoVITS 小中继：给浏览器补 CORS，并原样转发到 api_v2。

为什么需要它
------------
官方 `api_v2.py` 建的是裸 FastAPI（没有挂 CORSMiddleware）。
酒馆页面在 http://127.0.0.1:8000，直接 fetch http://127.0.0.1:9880 会被浏览器
以 CORS 拒绝（控制台报 "No 'Access-Control-Allow-Origin' header"）。
本脚本在中间转发一次，补上 CORS 头，其余字节原样透传（含流式 wav）。

用法
----
python gptsovits_relay.py                          # 9881 -> 9880
python gptsovits_relay.py --port 9881 --upstream 127.0.0.1:9880
python gptsovits_relay.py --upstream 192.168.1.5:9880   # GPT-SoVITS 跑在别的机器

只用标准库，不需要装任何东西。
"""
from __future__ import annotations

import argparse
import http.client
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ARGS = None

# 这些头由中继自己决定，不能照抄上游
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "access-control-allow-origin", "access-control-allow-headers", "access-control-allow-methods",
}

INDEX_HTML = """<!doctype html><meta charset="utf-8"><title>GPT-SoVITS relay</title>
<style>body{font-family:system-ui;margin:32px;background:#16161a;color:#e8e8ee}code{background:#25252c;padding:2px 6px;border-radius:4px}</style>
<h1>GPT-SoVITS relay</h1>
<p>上游：<code>UPSTREAM</code></p>
<p>把酒馆插件的地址填 <code>http://127.0.0.1:PORT</code> 即可。</p>
<p>自检：<a href="/__relay/health">/__relay/health</a></p>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "GPTSoVITS-Relay/1.0"

    def log_message(self, fmt, *args):  # noqa: A003
        pass

    # ---------- CORS ----------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------- 自检页 ----------
    def _local_only(self) -> bool:
        path = urlparse(self.path).path
        if path == "/__relay/health":
            body = json.dumps({"ok": True, "upstream": ARGS.upstream}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return True
        if path == "/" and self.command == "GET":
            html = INDEX_HTML.replace("UPSTREAM", ARGS.upstream).replace("PORT", str(ARGS.port))
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return True
        return False

    # ---------- 转发 ----------
    def _proxy(self):
        if self._local_only():
            return

        host, _, port = ARGS.upstream.partition(":")
        try:
            port_num = int(port or 9880)
        except ValueError:
            port_num = 9880

        body = None
        length = self.headers.get("Content-Length")
        if length:
            try:
                body = self.rfile.read(int(length))
            except (ValueError, OSError):
                body = None

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        conn = http.client.HTTPConnection(host, port_num, timeout=ARGS.timeout)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()

            self.send_response(resp.status)
            sent_length = False
            for key, value in resp.getheaders():
                low = key.lower()
                if low in HOP_BY_HOP:
                    continue
                if low == "content-length":
                    sent_length = True
                self.send_header(key, value)
            self._cors()

            upstream_length = resp.getheader("Content-Length")
            if upstream_length:
                self.send_header("Content-Length", upstream_length)
                self.end_headers()
                remaining = int(upstream_length)
                while remaining > 0:
                    chunk = resp.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
                return

            # 没有 Content-Length（流式 wav）→ 用 chunked 透传
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    self.wfile.write(b"%X\r\n" % len(chunk) + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
        except (ConnectionRefusedError, OSError) as exc:
            payload = json.dumps({"message": f"中继连不上 GPT-SoVITS（{ARGS.upstream}）：{exc}"},
                                 ensure_ascii=False).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self._cors()
            self.end_headers()
            self.wfile.write(payload)
        finally:
            conn.close()

    def do_GET(self):  # noqa: N802
        self._proxy()

    def do_POST(self):  # noqa: N802
        self._proxy()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="GPT-SoVITS CORS relay")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9881)
    p.add_argument("--upstream", default="127.0.0.1:9880", help="GPT-SoVITS api_v2 地址 host:port")
    p.add_argument("--timeout", type=int, default=600, help="转发超时（秒）")
    return p.parse_args(argv)


def main(argv=None):
    global ARGS
    ARGS = parse_args(argv)
    print(f"[relay] listen   : http://{ARGS.host}:{ARGS.port}", flush=True)
    print(f"[relay] upstream : {ARGS.upstream}", flush=True)
    print(f"[relay] 把酒馆插件的地址填成 http://{ARGS.host}:{ARGS.port}", flush=True)
    httpd = ThreadingHTTPServer((ARGS.host, ARGS.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[relay] bye", flush=True)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
