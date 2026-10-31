import glob, json, os, re
paths = [p for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")) if "/subagents/" not in p]
paths.sort(key=os.path.getmtime, reverse=True)
paths = paths[:300]
DECISION = re.compile(r"결정해\s*줄\s*것|결정\s*사항|결정할\s*것|골라\s*주|선택해\s*주")
ANYQ = re.compile(r"[가-힣a-zA-Z)`]\?")
TAILQ = re.compile(r"(까요|나요|습니까|을까|ㄹ까|할지)\s*\??\s*$|\?\s*$", re.M)
stats = dict(ask=0, typed_sessions=0, ends=0, ends_decision=0, ends_tail=0, ends_anyq=0, eof=0, eof_decision=0, eof_tail=0, mid=0, mid_tail=0)
samples = []
for path in paths:
    last = None
    typed_seen = False
    with open(path, errors="replace") as f:
        for line in f:
            try: row = json.loads(line)
            except ValueError: continue
            k = row.get("type"); m = row.get("message") or {}; c = m.get("content")
            if k == "assistant" and isinstance(c, list):
                texts = "\n".join(b.get("text", "") for b in c if b.get("type") == "text")
                uses = [b for b in c if b.get("type") == "tool_use"]
                stats["ask"] += sum(1 for u in uses if u.get("name") == "AskUserQuestion")
                if uses:
                    if texts:
                        stats["mid"] += 1
                        stats["mid_tail"] += bool(TAILQ.search(texts[-300:]))
                    last = None
                elif texts:
                    last = texts
            elif k == "user" and not row.get("isMeta"):
                typed = isinstance(c, str) or (isinstance(c, list) and any(b.get("type") == "text" for b in c) and not any(b.get("type") == "tool_result" for b in c))
                if typed:
                    typed_seen = True
                    if last is not None:
                        stats["ends"] += 1
                        d = bool(DECISION.search(last)); t = bool(TAILQ.search(last[-400:])); a = bool(ANYQ.search(last))
                        stats["ends_decision"] += d; stats["ends_tail"] += t; stats["ends_anyq"] += a
                        if (d or t) and len(samples) < 12:
                            samples.append(last[-110:].replace("\n", " / "))
                        last = None
    stats["typed_sessions"] += typed_seen
    if last is not None:
        stats["eof"] += 1
        stats["eof_decision"] += bool(DECISION.search(last))
        stats["eof_tail"] += bool(TAILQ.search(last[-400:]))
print(stats)
for s in samples: print("-", s)
