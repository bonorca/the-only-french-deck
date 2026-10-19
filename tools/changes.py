"""What changed in the deck between a git revision and the working tree (or two revisions), from deck-source/tracking.
Prints a short Chinese summary, ready for release notes. Standard library only.
Usage: python tools/changes.py [OLD_REV] [NEW_REV]   (defaults: the latest tag, the working tree; a folder of tracking files also works)"""
import csv, io, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = "deck-source/tracking"
KEYS = {"words.tsv": 1, "meanings.tsv": 1, "conjugations.tsv": 1, "examples.tsv": 2, "audio.tsv": 1}


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout


def load(rev, name):
    if rev is None or os.path.isdir(rev):                              # working tree, or a folder holding tracking files
        p = os.path.join(rev, name) if rev else os.path.join(ROOT, T, name)
        txt = open(p, encoding="utf-8").read() if os.path.exists(p) else None
    else:
        r = subprocess.run(["git", "show", f"{rev}:{T}/{name}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        txt = r.stdout if r.returncode == 0 else None
    if txt is None: return None
    rows = list(csv.reader(io.StringIO(txt), delimiter="\t", quoting=csv.QUOTE_NONE))[1:]
    k = KEYS[name]
    return {tuple(r[:k]): r[k:] for r in rows if r}


def names(keys, n=12):
    keys = sorted({k[0] for k in keys}, key=str.casefold)
    return "、".join(keys[:n]) + (f" 等 {len(keys)} 个" if len(keys) > n else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tags = git("tag", "--sort=-v:refname").split()
    old = sys.argv[1] if len(sys.argv) > 1 else (tags[0] if tags else "HEAD")
    new = sys.argv[2] if len(sys.argv) > 2 else None
    print(f"对比 {old} → {new or '工作区'}")
    D = {n: (load(old, n), load(new, n)) for n in KEYS}
    if D["words.tsv"][0] is None:
        print(f"（{old} 里还没有 tracking 清单，没法对比；从下一个带清单的版本起就可以了）"); return
    a, b = D["words.tsv"]
    if set(b) - set(a): print("新增词：" + names(set(b) - set(a)))
    if set(a) - set(b): print("删除词：" + names(set(a) - set(b)))
    for n, label in (("words.tsv", "标题 / 音标 / 标签"), ("meanings.tsv", "释义"), ("conjugations.tsv", "变位")):
        a, b = D[n]
        ch = {k for k in set(a) & set(b) if a[k] != b[k]}
        added = {k for k in set(b) - set(a) if k in D["words.tsv"][0]}
        if ch or added: print(f"{label}改了 {len(ch | added)} 个词：" + names(ch | added))
    a, b = D["examples.tsv"]
    txt = {k for k in set(a) & set(b) if a[k][:2] != b[k][:2]}
    if txt: print(f"例句文字改了 {len(txt)} 句：" + names(txt))
    if set(b) - set(a): print(f"新增例句 {len(set(b) - set(a))} 句")
    if set(a) - set(b): print(f"删除例句 {len(set(a) - set(b))} 句")
    a, b = D["audio.tsv"]
    kind = lambda v: "例句" if "(example" in v[-1] else "单词"
    for label, keys in (("新增", set(b) - set(a)), ("删除", set(a) - set(b)), ("重做", {k for k in set(a) & set(b) if a[k][0] != b[k][0]})):
        if not keys: continue
        src = b if label != "删除" else a
        by = {}
        for k in keys: by.setdefault(kind(src[k]), []).append(k[0])
        for kd, fs in sorted(by.items()):
            fs.sort(key=str.casefold)
            print(f"{kd}音频{label} {len(fs)} 个" + ("：" + "、".join(fs) if len(fs) <= 20 else ""))


if __name__ == "__main__":
    main()
