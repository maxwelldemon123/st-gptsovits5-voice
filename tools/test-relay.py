#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中继契约测试：起「假上游 + 中继」，逐条验证 CORS / 转发 / 流式透传。

python tools/test-relay.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
UP_PORT, RELAY_PORT = 9882, 9881
PASSED = 0
FAILED: list[str] = []


def check(name, ok, detail=""):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILED.append(f"{name}{('  ' + detail) if detail else ''}")


def req(url, method="GET", payload=None, timeout=20):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def wait_port(port, tries=60):
    for _ in range(tries):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/__relay/health", timeout=1).read()
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def main() -> int:
    log = open(ROOT / "relay-test.log", "wb")
    up = subprocess.Popen([PY, str(ROOT / "tools" / "fake_upstream.py"), "--port", str(UP_PORT)],
                          stdout=log, stderr=log)
    relay = subprocess.Popen([PY, str(ROOT / "server" / "gptsovits_relay.py"),
                              "--port", str(RELAY_PORT), "--upstream", f"127.0.0.1:{UP_PORT}"],
                             stdout=log, stderr=log)
    try:
        if not wait_port(RELAY_PORT):
            print("中继没起来，详见 relay-test.log", file=sys.stderr)
            return 2
        base = f"http://127.0.0.1:{RELAY_PORT}"

        status, headers, body = req(f"{base}/__relay/health")
        check("中继自检页 200", status == 200, f"status={status}")
        check("自检页含 upstream", b"upstream" in body)

        status, headers, _ = req(f"{base}/tts", method="OPTIONS")
        check("OPTIONS 204", status == 204, f"status={status}")
        check("OPTIONS 带 CORS", headers.get("Access-Control-Allow-Origin") == "*",
              str(headers.get("Access-Control-Allow-Origin")))
        check("OPTIONS 允许 POST", "POST" in (headers.get("Access-Control-Allow-Methods") or ""))

        status, headers, body = req(f"{base}/control")
        check("GET /control 透传 400", status == 400, f"status={status}")
        check("400 也带 CORS", headers.get("Access-Control-Allow-Origin") == "*")

        status, _, body = req(f"{base}/set_gpt_weights?weights_path=A/x.ckpt")
        check("切 GPT 权重 200", status == 200 and b"success" in body, f"status={status} {body[:60]!r}")
        status, _, body = req(f"{base}/set_sovits_weights?weights_path=A/x.pth")
        check("切 SoVITS 权重 200", status == 200 and b"success" in body, f"status={status}")

        payload = {
            "text": "呜…主人…！", "text_lang": "zh",
            "ref_audio_path": "refs/xiaod.wav", "prompt_text": "はい、そうです",
            "prompt_lang": "ja", "media_type": "wav", "streaming_mode": 0, "speed_factor": 1.0,
        }
        status, headers, body = req(f"{base}/tts", method="POST", payload=payload)
        check("POST /tts 200", status == 200, f"status={status} {body[:80]!r}")
        check("POST 带 CORS", headers.get("Access-Control-Allow-Origin") == "*")
        check("Content-Type 是 wav", (headers.get("Content-Type") or "").startswith("audio/wav"),
              str(headers.get("Content-Type")))
        ok_wav = False
        frames = 0
        if body[:4] == b"RIFF":
            with wave.open(io.BytesIO(body), "rb") as wf:
                frames = wf.getnframes()
            ok_wav = frames > 0
        check("返回可解析 wav", ok_wav, f"frames={frames}")
        check("Content-Length 与实际一致",
              str(len(body)) == headers.get("Content-Length"), f"{len(body)} vs {headers.get('Content-Length')}")

        bad = dict(payload)
        bad["text"] = ""
        status, _, body = req(f"{base}/tts", method="POST", payload=bad)
        check("缺 text 透传 400", status == 400, f"status={status} {body[:80]!r}")

        status, headers, body = req(f"{base}/stream")
        check("流式响应 200", status == 200, f"status={status}")
        check("流式长度正确（chunked 透传）", len(body) == 64000, f"{len(body)}")
        check("流式带 CORS", headers.get("Access-Control-Allow-Origin") == "*")

        print(f"通过 {PASSED} 项")
        if FAILED:
            print(f"失败 {len(FAILED)} 项：")
            for item in FAILED:
                print(" -", item)
            return 1
        print("全部通过 ✅")
        return 0
    finally:
        for proc in (relay, up):
            proc.terminate()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
