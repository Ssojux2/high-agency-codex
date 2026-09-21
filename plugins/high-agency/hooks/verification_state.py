#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
VERIFY_RE = re.compile(r"(?:\bpytest\b|python\s+-m\s+pytest|\bjest\b|\bvitest\b|playwright\s+test|cypress\s+run|cargo\s+(?:test|check)|go\s+test|dotnet\s+test|mvnw?\b.*\btest\b|gradlew?\b.*\btest\b|\brspec\b|swift\s+test|xcodebuild\b.*\btest\b|\b(?:npm|pnpm|yarn|bun)\b.*\b(?:test|lint|typecheck|check|build)\b|\btsc\b|\beslint\b|\bruff\b|\bmypy\b|\bpyright\b)", re.I)
DIFF_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?diff\b", re.I)
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$", re.M)

def state_dir(): return Path(os.environ.get("PLUGIN_DATA") or ".").resolve() / "verification"
def key(p): return str(p.get("turn_id") or p.get("session_id") or "default")
def path_for(p): return state_dir() / (re.sub(r"[^A-Za-z0-9_.-]","_",key(p))[:120] + ".json")
def load(p):
    try: return json.loads(p.read_text())
    except Exception: return {}
def save(p,d):
    p.parent.mkdir(parents=True, exist_ok=True)
    t=p.with_suffix(".tmp")
    t.write_text(json.dumps(d,separators=(",",":")))
    t.replace(p)
def active_prompt(prompt):
    q=prompt.lower()
    return "high-agency" in q or "high agency" in q or "bounded-autonomy" in q
def extract_paths(tool_name, tool_input):
    if not isinstance(tool_input,dict): return []
    out=[]
    for f in ("file_path","path","notebook_path"):
        v=tool_input.get(f)
        if isinstance(v,str) and v: out.append(v)
    if tool_name=="apply_patch":
        c=tool_input.get("command")
        if isinstance(c,str): out += PATCH_PATH_RE.findall(c)
    return out

def main():
    try: payload=json.load(sys.stdin)
    except Exception: return 0
    event=str(payload.get("hook_event_name") or "")
    path=path_for(payload)
    if event=="UserPromptSubmit":
        prompt=str(payload.get("prompt") or payload.get("user_prompt") or "")
        save(path, {"active":active_prompt(prompt),"edited_files":[],"all_edited_files":[],"dirty_since_verification":False,"verification_commands":[],"diff_review_seen":False,"verification_guard_warned":False,"diff_guard_warned":False})
        return 0
    if event!="PostToolUse": return 0
    data=load(path)
    if not data.get("active"): return 0
    tool_name=str(payload.get("tool_name") or "")
    tool_input=payload.get("tool_input")
    edited=list(data.get("edited_files") or [])
    if tool_name in {"Edit","Write","NotebookEdit","apply_patch"}:
        paths=extract_paths(tool_name,tool_input)
        if paths:
            all_edited=list(data.get("all_edited_files") or [])
            for item in paths:
                if item not in edited: edited.append(item)
                if item not in all_edited: all_edited.append(item)
            data["edited_files"]=edited[:64]
            data["all_edited_files"]=all_edited[:128]
            data["dirty_since_verification"]=True
            data["diff_review_seen"]=False
            data["verification_guard_warned"]=False
            data["diff_guard_warned"]=False
    if tool_name=="Bash" and isinstance(tool_input,dict):
        cmd=tool_input.get("command")
        if isinstance(cmd,str):
            if VERIFY_RE.search(cmd):
                data["dirty_since_verification"]=False
                cmds=list(data.get("verification_commands") or [])
                cmds.append(cmd[:300])
                data["verification_commands"]=cmds[-8:]
            if DIFF_RE.search(cmd):
                data["diff_review_seen"]=True
    save(path,data)
    return 0
if __name__=="__main__": raise SystemExit(main())
