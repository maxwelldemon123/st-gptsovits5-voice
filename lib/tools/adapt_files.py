#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v1.1 的三份文件适配到「GPT-SoVITS v5 角色配音台」。

原则：**能不改就不改**。
  - 聊天：只重写首行的 chat_metadata（追加 gptsovits5 块），其余 529 行逐字节保持原样
  - 世界书：只追加顶层 extensions.gptsovits5，29 条条目原样
  - 角色卡：见 card_v12.py（只加 data.extensions.gptsovits5 + 版本号）

用法：
  python tools/adapt_files.py \
      --chat   "D:\\...\\v1.1\\Demon（小d）-统一版.jsonl" \
      --book   "D:\\...\\v1.1\\小鲸鱼娘 · 设定与细节-统一版.json" \
      --out-dir "E:\\dshwork\\小鲸鱼娘\\v1.2" \
      --character 小鲸鱼娘 \
      --slots "xiaod:小d · 柔软,demon:demon · 小恶魔" --default-slot xiaod
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

CARD_KEY = "gptsovits5"
OLD_KEY = "indextts25"


def parse_slots(spec: str) -> list[dict]:
    out, seen = [], set()
    for chunk in str(spec or "").replace("；", ",").replace(";", ",").split(","):
        piece = chunk.strip()
        if not piece:
            continue
        if ":" in piece:
            raw_id, label = piece.split(":", 1)
        elif "：" in piece:
            raw_id, label = piece.split("：", 1)
        else:
            raw_id, label = piece, piece
        sid, lab = raw_id.strip(), (label.strip() or raw_id.strip())
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append({"id": sid, "label": lab})
    return out


def slot_block(character: str, slots: list[dict], default_slot: str) -> dict:
    return {"version": 1, "character": character, "defaultSlot": default_slot, "slots": slots}


def adapt_chat(src: Path, dst: Path, block: dict) -> dict:
    raw = src.read_text(encoding="utf-8")
    lines = [l for l in raw.split("\n") if l.strip()]
    head = json.loads(lines[0])
    meta = head.get("chat_metadata")
    if not isinstance(meta, dict):
        meta = {}
    before = json.dumps(meta.get(CARD_KEY), ensure_ascii=False)
    meta[CARD_KEY] = block
    head["chat_metadata"] = meta

    new_lines = [json.dumps(head, ensure_ascii=False, separators=(",", ":"))] + lines[1:]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(new_lines), encoding="utf-8", newline="\n")

    unchanged = sum(1 for a, b in zip(lines[1:], new_lines[1:]) if a == b)
    return {
        "messages": len(lines) - 1,
        "unchanged_lines": unchanged,
        "block_changed": before != json.dumps(block, ensure_ascii=False),
        "kept_old_key": OLD_KEY in meta,
    }


def adapt_book(src: Path, dst: Path, block: dict) -> dict:
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    entries_before = json.loads(json.dumps(data.get("entries")))
    ext = data.get("extensions")
    if not isinstance(ext, dict):
        ext = {}
    ext[CARD_KEY] = block
    data["extensions"] = ext

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    after = json.loads(dst.read_text(encoding="utf-8"))
    same_entries = json.loads(json.dumps(after.get("entries"))) == entries_before
    return {
        "entries": len(after.get("entries") or []),
        "entries_unchanged": same_entries,
        "kept_old_key": OLD_KEY in (after.get("extensions") or {}),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", required=True)
    ap.add_argument("--book", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--character", required=True)
    ap.add_argument("--slots", required=True)
    ap.add_argument("--default-slot", default=None)
    ap.add_argument("--chat-name", default=None)
    ap.add_argument("--book-name", default=None)
    args = ap.parse_args(argv)

    slots = parse_slots(args.slots)
    if not slots:
        print("声线解析为空", file=sys.stderr)
        return 2
    default_slot = args.default_slot or slots[0]["id"]
    if default_slot not in {s["id"] for s in slots}:
        print("默认声线不在声线表里", file=sys.stderr)
        return 2

    block = slot_block(args.character, slots, default_slot)
    out = Path(args.out_dir)
    chat_in, book_in = Path(args.chat), Path(args.book)
    chat_out = out / (args.chat_name or f"{chat_in.stem}-GPTSoVITS版.jsonl")
    book_out = out / (args.book_name or f"{book_in.stem}-GPTSoVITS版.json")

    chat_stat = adapt_chat(chat_in, chat_out, block)
    book_stat = adapt_book(book_in, book_out, block)

    print("== 聊天 ==")
    print(f"  {chat_out}")
    print(f"  消息 {chat_stat['messages']} 条，逐字节未变 {chat_stat['unchanged_lines']} 条"
          f"（应为 {chat_stat['messages']}）")
    print(f"  追加 chat_metadata.{CARD_KEY}：{'是' if chat_stat['block_changed'] else '已存在且相同'}")
    print(f"  保留旧键 {OLD_KEY}：{'是' if chat_stat['kept_old_key'] else '否'}")
    print("== 世界书 ==")
    print(f"  {book_out}")
    print(f"  条目 {book_stat['entries']} 条，内容未变：{'是' if book_stat['entries_unchanged'] else '否'}")
    print(f"  追加 extensions.{CARD_KEY}；保留旧键 {OLD_KEY}：{'是' if book_stat['kept_old_key'] else '否'}")

    ok = (chat_stat["unchanged_lines"] == chat_stat["messages"]) and book_stat["entries_unchanged"]
    if not ok:
        print("自检失败：有非预期改动", file=sys.stderr)
        return 1
    print("自检通过 ✅（除新增的 gptsovits5 块外，零改动）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
