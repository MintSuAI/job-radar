#!/usr/bin/env python3
"""job-radar 通用招聘板扫描器（config 驱动，多 profile 复用）

用法: python3 jobboard_scan.py <profile目录>
读取 <profile目录>/boards.json:
{
  "greenhouse": ["stripe", "okx"],
  "lever": ["crypto"],
  "ashby": ["rogo"],
  "loc_ok": "hong\\s*kong|london|dublin",
  "title_ok": "product|risk|solution",
  "title_block": "engineer|designer|intern\\b"
}
与 <profile目录>/.snapshot.json diff, 输出 新增/下架/全量。
"""
import json, re, sys, os, datetime, subprocess

def fetch(url, timeout=30, retries=3):
    for _ in range(retries):
        p = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-A", "Mozilla/5.0", url],
                           capture_output=True, text=True)
        if p.returncode == 0 and p.stdout:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                pass
    raise RuntimeError(f"fetch failed: {url}")

def scan(cfg):
    loc_ok = re.compile(cfg["loc_ok"], re.I)
    title_ok = re.compile(cfg["title_ok"], re.I)
    title_block = re.compile(cfg.get("title_block", r"$^"), re.I)
    found = {}
    def keep(t, loc):
        return loc_ok.search(loc) and title_ok.search(t) and not title_block.search(t)
    for b in cfg.get("greenhouse", []):
        try:
            for j in fetch(f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs").get("jobs", []):
                if keep(j["title"], j["location"]["name"]):
                    found[f"gh:{b}:{j['id']}"] = f"{b} | {j['title']} | {j['location']['name']} | {j['absolute_url']}"
        except Exception as e:
            print(f"[warn] greenhouse/{b}: {e}", file=sys.stderr)
    for b in cfg.get("lever", []):
        try:
            for j in fetch(f"https://api.lever.co/v0/postings/{b}?mode=json"):
                loc = j.get("categories", {}).get("location", "") or ""
                if keep(j.get("text", ""), loc):
                    found[f"lv:{b}:{j['id']}"] = f"{b} | {j['text']} | {loc} | {j['hostedUrl']}"
        except Exception as e:
            print(f"[warn] lever/{b}: {e}", file=sys.stderr)
    for b in cfg.get("ashby", []):
        try:
            for j in fetch(f"https://api.ashbyhq.com/posting-api/job-board/{b}?includeCompensation=false").get("jobs", []):
                loc = j.get("location", "") or ""
                sec = " ".join(a.get("location", "") for a in j.get("secondaryLocations", []))
                if keep(j.get("title", ""), loc + " " + sec):
                    found[f"ab:{b}:{j['id']}"] = f"{b} | {j['title']} | {loc} | {j.get('jobUrl','')}"
        except Exception as e:
            print(f"[warn] ashby/{b}: {e}", file=sys.stderr)
    return found

def main():
    if len(sys.argv) < 2:
        sys.exit("用法: jobboard_scan.py <profile目录>")
    pdir = os.path.abspath(sys.argv[1])
    with open(os.path.join(pdir, "boards.json")) as f:
        cfg = json.load(f)
    snap_path = os.path.join(pdir, ".snapshot.json")
    prev = {}
    if os.path.exists(snap_path):
        with open(snap_path) as f:
            prev = json.load(f)
    found = scan(cfg)
    new = {k: v for k, v in found.items() if k not in prev}
    gone = {k: v for k, v in prev.items() if k not in found}
    print(f"=== job-radar 扫描 {datetime.date.today().isoformat()} ({os.path.basename(pdir)}) ===")
    print(f"匹配总数: {len(found)} | 新增: {len(new)} | 下架: {len(gone)}")
    if new:
        print("\n--- 新增 ---")
        for v in sorted(new.values()): print("+", v)
    if gone:
        print("\n--- 下架 ---")
        for v in sorted(gone.values()): print("-", v)
    if not new and not gone:
        print("无变化。")
    with open(snap_path, "w") as f:
        json.dump(found, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
