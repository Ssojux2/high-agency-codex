#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
MARKER_RE=re.compile(r"<!--\s*high-agency:continue(?:\s+max=(\d+))?\s*-->\s*$", re.I|re.S)
DEFAULT_MAX=3
HARD_CAP=12
STATE_TTL_SECONDS=7*24*60*60
LARGE_DIFF_LINES=120
DOC_EXTS={".md",".mdx",".txt",".rst",".adoc",".png",".jpg",".jpeg",".gif",".svg",".webp",".ico"}
DOC_NAMES={"LICENSE","README","CHANGELOG","CONTRIBUTING","CODE_OF_CONDUCT"}
RISK_RE=re.compile(r"(^|/)(migrations?|schema|auth|security|permissions?|policies?|\.github/workflows)(/|$)|(^|/)(package\.json|pyproject\.toml|cargo\.toml|go\.mod|go\.sum|pom\.xml|dockerfile|docker-compose\.(?:yml|yaml)|[^/]*lock[^/]*)$", re.I)

def emit(p): sys.stdout.write(json.dumps(p,separators=(",",":"))+"\n")
def root(): return Path(os.environ.get("PLUGIN_DATA") or ".").resolve()
def bpath(turn): return root()/"bounded-autonomy"/(hashlib.sha256(turn.encode()).hexdigest()[:24]+".json")
def vpath(payload):
    raw=str(payload.get("turn_id") or payload.get("session_id") or "default")
    safe=re.sub(r"[^A-Za-z0-9_.-]","_",raw)[:120]
    return root()/"verification"/(safe+".json")
def load(p):
    try:return json.loads(p.read_text())
    except Exception:return {}
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(".tmp")
    t.write_text(json.dumps(d,separators=(",",":")))
    t.replace(p)
def clear(p):
    try:p.unlink(missing_ok=True)
    except OSError:pass
def cleanup(d):
    if not d.exists():return
    cutoff=time.time()-STATE_TTL_SECONDS
    for p in d.glob("*.json"):
        try:
            if p.stat().st_mtime<cutoff:p.unlink(missing_ok=True)
        except OSError:pass
def code_files(files):
    out=[]
    for raw in files:
        p=Path(raw); n=p.name
        if n.upper() in DOC_NAMES or n.startswith("README") or p.suffix.lower() in DOC_EXTS: continue
        out.append(raw)
    return out
def rel(raw,cwd):
    p=Path(raw)
    try:
        if p.is_absolute(): return p.resolve().relative_to(cwd.resolve()).as_posix()
    except Exception: pass
    return p.as_posix().lstrip("./")
def git_stats(cwd,files):
    if not files:return 0,""
    try:
        cp=subprocess.run(["git","diff","--numstat","HEAD","--",*files],cwd=cwd,text=True,capture_output=True,timeout=.8)
        total=0
        if cp.returncode==0:
            for line in cp.stdout.splitlines():
                parts=line.split("\t")
                if len(parts)>=2:
                    a,d=parts[0],parts[1]
                    if a.isdigit(): total+=int(a)
                    if d.isdigit(): total+=int(d)
        ck=subprocess.run(["git","diff","--check","HEAD","--",*files],cwd=cwd,text=True,capture_output=True,timeout=.8)
        return total,(ck.stdout+ck.stderr).strip()[:1200] if ck.returncode else ""
    except Exception:return 0,""
def diff_reasons(files,cwd):
    cf=code_files(files)
    reasons=[]
    if len(cf)>=3: reasons.append(f"{len(cf)} code/config files changed")
    rels=[rel(x,cwd) for x in cf]
    tops={r.split("/")[0] if "/" in r else "." for r in rels}
    if len(cf)>=2 and len(tops)>=2: reasons.append("change crosses module boundaries")
    if any(RISK_RE.search(r) for r in rels): reasons.append("high-impact/shared path changed")
    lines,check=git_stats(cwd,cf)
    if lines>=LARGE_DIFF_LINES: reasons.append(f"large diff ({lines} changed lines)")
    return reasons,cf,check
def reset_pass(p,d):
    if not d.get("active"):return
    d["edited_files"]=[]
    d["dirty_since_verification"]=False
    d["verification_commands"]=[]
    d["verification_guard_warned"]=False
    save(p,d)

def main():
    try:payload=json.load(sys.stdin)
    except Exception:
        emit({})
        return 0
    turn=str(payload.get("turn_id") or "")
    msg=payload.get("last_assistant_message")
    cwd=Path(payload.get("cwd") or ".").resolve()
    if not turn or not isinstance(msg,str):
        emit({})
        return 0
    cleanup(root()/"bounded-autonomy")
    cleanup(root()/"verification")
    bp=bpath(turn)
    vp=vpath(payload)
    vd=load(vp)
    marker=MARKER_RE.search(msg)
    pass_files=list(vd.get("edited_files") or [])
    if vd.get("active") and code_files(pass_files) and vd.get("dirty_since_verification") and not vd.get("verification_guard_warned"):
        vd["verification_guard_warned"]=True
        save(vp,vd)
        suffix=""
        if marker:
            lim=min(max(int(marker.group(1) or DEFAULT_MAX),1),HARD_CAP)
            suffix=f" If more work remains after verification, preserve <!-- high-agency:continue max={lim} -->."
        emit({"decision":"block","reason":"High Agency verification guard: relevant edits occurred after the last verification. Run the narrowest relevant targeted/affected check. Do not run the full suite unless risk justifies it."+suffix})
        return 0
    if not marker and vd.get("active") and not vd.get("diff_review_seen") and not vd.get("diff_guard_warned"):
        reasons,cf,check=diff_reasons(list(vd.get("all_edited_files") or []),cwd)
        if reasons:
            vd["diff_guard_warned"]=True
            save(vp,vd)
            preview=", ".join(rel(x,cwd) for x in cf[:8])
            extra=(" git diff --check also reported: "+check) if check else ""
            emit({"decision":"block","reason":"High Agency conditional diff review: "+"; ".join(reasons)+". Inspect only the focused final diff for touched files ("+preview+"), confirm no unrelated changes/API drift, then finish. Do not launch a reviewer subagent or broad branch review unless requested."+extra})
            return 0
    if not marker:
        clear(bp)
        clear(vp)
        emit({})
        return 0
    lim=min(max(int(marker.group(1) or DEFAULT_MAX),1),HARD_CAP)
    bd=load(bp)
    count=max(0,int(bd.get("continuations",0)))
    if count>=lim:
        clear(bp)
        clear(vp)
        emit({})
        return 0
    count+=1
    save(bp,{"continuations":count,"limit":lim,"updated_at":int(time.time())})
    reset_pass(vp,vd)
    if count==lim:
        reason=f"Final bounded-autonomy continuation {count}/{lim}. Make the highest-value remaining progress, verify only the touched/affected scope unless risk requires broader checks, do not emit another continuation marker, and report the evidence or blocker."
    else:
        reason=f"Bounded-autonomy continuation {count}/{lim}. Continue from current repository state. Use an independently verifiable step and targeted/affected verification. Request another pass only after meaningful new progress; if needed end with <!-- high-agency:continue max={lim} -->."
    emit({"decision":"block","reason":reason})
    return 0
if __name__=="__main__":raise SystemExit(main())
