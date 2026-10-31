"""최근 세션 기록에서 AskUserQuestion 호출과 턴 마지막 본문의 질문 표현을 센다.

본문 질문 판정은 정규식 어림이다. 이 수는 비율의 크기를 보는 데만 쓴다.
"""
import glob
import json
import os
import re
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
paths = [
    p
    for p in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
    if "/subagents/" not in p
]
paths.sort(key=os.path.getmtime, reverse=True)
paths = paths[:N]

DECISION = re.compile(r"결정해\s*줄\s*것|결정\s*사항|결정할\s*것|골라\s*주|선택해\s*주")
ASKING = re.compile(r"(할까요|될까요|까요\?|인가요\?|습니까\?|주세요\?|\?)\s*$", re.M)

asks = 0
turn_ends = 0
decision_ends = 0
asking_ends = 0
either_ends = 0
sessions = 0
bytes_read = 0

for path in paths:
    last_text = None
    sessions += 1
    bytes_read += os.path.getsize(path)
    with open(path, errors="replace") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            kind = row.get("type")
            message = row.get("message") or {}
            content = message.get("content")
            if kind == "assistant" and isinstance(content, list):
                texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                uses = [b for b in content if b.get("type") == "tool_use"]
                asks += sum(1 for u in uses if u.get("name") == "AskUserQuestion")
                if uses:
                    last_text = None
                elif texts:
                    last_text = "\n".join(texts)
            elif kind == "user" and not row.get("isMeta"):
                typed = isinstance(content, str) or (
                    isinstance(content, list)
                    and any(b.get("type") == "text" for b in content)
                    and not any(b.get("type") == "tool_result" for b in content)
                )
                if typed and last_text is not None:
                    turn_ends += 1
                    is_decision = bool(DECISION.search(last_text))
                    is_asking = bool(ASKING.search(last_text[-400:]))
                    decision_ends += is_decision
                    asking_ends += is_asking
                    either_ends += is_decision or is_asking
                    last_text = None

print(f"sessions={sessions} bytes={bytes_read}")
print(f"AskUserQuestion calls={asks}")
print(f"turn ends followed by a typed prompt={turn_ends}")
print(f"  decision wording={decision_ends}")
print(f"  question at the tail={asking_ends}")
print(f"  either={either_ends}")
