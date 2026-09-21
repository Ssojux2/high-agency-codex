#!/usr/bin/env python3
import json, statistics, sys
from collections import defaultdict
from pathlib import Path

def rows_from(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data,list) else [data]

def med(vals):
    vals=[v for v in vals if isinstance(v,(int,float))]
    return round(statistics.median(vals),2) if vals else None

def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: python3 evals/compare.py result.json [...]")
    groups=defaultdict(list)
    for f in sys.argv[1:]:
        for row in rows_from(f):
            groups[str(row.get("variant","unknown"))].append(row)
    out=[]
    for variant,rs in sorted(groups.items()):
        n=len(rs)
        success=sum(bool(r.get("task_success")) for r in rs)
        scores=[r.get("score") for r in rs if isinstance(r.get("score"),(int,float))]
        out.append({
            "variant":variant,
            "runs":n,
            "success_rate":round(success/n,3) if n else None,
            "median_score":med(scores),
            "median_tool_calls":med([r.get("tool_calls") for r in rs]),
            "median_tokens_total":med([r.get("tokens_total") for r in rs]),
            "median_continuation_passes":med([r.get("continuation_passes") for r in rs]),
            "false_completion_rate":round(sum(bool(r.get("false_completion")) for r in rs)/n,3) if n else None,
            "no_progress_passes_total":sum(int(r.get("no_progress_passes",0) or 0) for r in rs),
            "full_verification_rate":round(sum(r.get("verification_scope")=="full" for r in rs)/n,3) if n else None
        })
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    main()
