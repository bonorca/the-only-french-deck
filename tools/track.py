"""Plain-text snapshots of the deck for readable GitHub diffs, generated from deck-source/notes.txt (+ the media folder).
One line per word / example / audio file, HTML stripped, sorted by word, so a changed meaning, example, conjugation or
re-recorded audio shows up as a one-line diff. Standard library only.
  deck-source/tracking/words.tsv          word, headword as shown, IPA, tags
  deck-source/tracking/meanings.tsv       word, meanings (parts of speech, forms, cf.)
  deck-source/tracking/examples.tsv       word, n, French, Chinese (their audio is listed in audio.tsv)
  deck-source/tracking/conjugations.tsv   word, conjugation
  deck-source/tracking/audio.tsv          file, sha256 (12 hex), bytes, word, where it is used
Usage: python tools/track.py [--media <collection.media dir>] [--src notes.txt] [--out dir]   (default media: the Anki profile's)"""
import argparse, csv, hashlib, html, os, re, sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "deck-source", "notes.txt")
OUT = os.path.join(ROOT, "deck-source", "tracking")
FIELDS = ["guid", "Word", "Word with article", "IPA", "Basic meanings of word", "Example sentences", "audio", "Conjugation", "tags"]
BLOCK = {"div", "table", "tr", "p", "br", "li", "ul", "ol", "details", "summary"}


class Text(HTMLParser):
    """HTML -> one line: blocks become " | ", cells a space, part-of-speech pills 【…】, play buttons dropped."""
    def __init__(self):
        super().__init__(convert_charrefs=True); self.out = []; self.stack = []; self.cell = 0
    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "") or ""
        if tag in BLOCK: self.out.append(" | ")
        if tag == "tr": self.cell = 0
        if tag in ("td", "th"): self.out.append(" / " if self.cell else " "); self.cell += 1
        if tag == "span" and "pos" in cls.split(): self.out.append("【")
        if tag == "span" and "sep" in cls.split(): self.out.append(" ")
        self.stack.append((tag, cls))
    def handle_endtag(self, tag):
        while self.stack:
            t, cls = self.stack.pop()
            if t == "span" and "pos" in cls.split(): self.out.append("】")
            if t == tag: break
        if tag in BLOCK: self.out.append(" | ")
    def handle_data(self, data): self.out.append(data)
    def text(self):
        s = re.sub(r"\s+", " ", "".join(self.out).replace(" ", " "))
        s = re.sub(r"(\s*\|\s*)+", " | ", s).strip(" |")
        s = re.sub(r"\s*·\s*", " · ", s)
        return re.sub(r"【\s*", "【", re.sub(r"\s*】\s*", "】", s))


def text(fragment):
    p = Text(); p.feed(fragment or ""); p.close(); return p.text()


def conj_text(fragment):
    """Conjugation block -> '现在时: je mange, tu manges, … | 复合过去时: avoir mangé | 将来时词根: ir-'."""
    out = []
    for tb in re.split(r'<div class="tb">', fragment or "")[1:]:
        m = re.search(r'<span class="pos">(.*?)</span>', tb, re.S)
        label = text(m.group(1)) if m else ""
        body = tb[m.end():] if m else tb
        if "<table" in body:
            rows = re.findall(r"<tr>(.*?)</tr>", body, re.S)
            body_t = ", ".join(" ".join(text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)).replace("' ", "'") for r in rows)
        else:
            body_t = text(body)
        out.append(f"{label}: {body_t}" if label else body_t)
    return " | ".join(out) if out else text(fragment)


def media_refs(field):
    return re.findall(r"\[sound:(.+?)\]", field) + [html.unescape(m) for m in re.findall(r'<audio[^>]*\bsrc="([^"]+)"', field)]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", default=os.path.join(os.environ.get("APPDATA", ""), "Anki2", "账户 1", "collection.media"))
    ap.add_argument("--src", default=SRC); ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    lines = [l for l in open(a.src, encoding="utf-8", newline="") if not l.startswith("#")]
    rows = [dict(zip(FIELDS, r)) for r in csv.reader(lines, delimiter="\t", quotechar='"')]
    seen = {}
    for r in sorted(rows, key=lambda r: r["guid"]):                      # same spelling twice: word, word #2 (stable by guid)
        seen[r["Word"]] = seen.get(r["Word"], 0) + 1
        r["key"] = r["Word"] if seen[r["Word"]] == 1 else f'{r["Word"]} #{seen[r["Word"]]}'
    rows.sort(key=lambda r: (r["key"].casefold(), r["key"]))
    os.makedirs(a.out, exist_ok=True)
    def write(name, header, data):
        with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write("\t".join(header) + "\n")
            for row in data: f.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in row) + "\n")
    write("words.tsv", ["word", "headword", "ipa", "tags"],
          [(r["key"], text(r["Word with article"]), r["IPA"], r["tags"]) for r in rows])
    write("meanings.tsv", ["word", "meanings"], [(r["key"], text(r["Basic meanings of word"])) for r in rows])
    ex = []
    for r in rows:
        for n, (fr, zh) in enumerate(re.findall(r'<div class="fr">(.*?)</div><div class="zh">(.*?)</div>', r["Example sentences"], re.S), 1):
            ex.append((r["key"], n, text(fr), text(zh)))
    write("examples.tsv", ["word", "n", "french", "chinese"], ex)
    write("conjugations.tsv", ["word", "conjugation"], [(r["key"], conj_text(r["Conjugation"])) for r in rows if r["Conjugation"].strip()])
    use = {}
    for r in rows:
        for fld, where in (("audio", "word"), ("Basic meanings of word", "form"), ("Example sentences", "example"), ("Conjugation", "conjugation")):
            refs = media_refs(r[fld])
            if fld == "Example sentences":
                for n, fr in enumerate(re.findall(r'<div class="fr">(.*?)</div>', r[fld], re.S), 1):
                    for m in media_refs(fr): use.setdefault(m, []).append(f'{r["key"]} (example {n})')
                continue
            for m in refs: use.setdefault(m, []).append(f'{r["key"]} ({where})')
    aud, missing = [], 0
    for fn in sorted(use, key=str.casefold):
        p = os.path.join(a.media, fn)
        if os.path.exists(p):
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]; size = os.path.getsize(p)
        else:
            h, size = "MISSING", 0; missing += 1
        aud.append((fn, h, size, "; ".join(use[fn])))
    write("audio.tsv", ["file", "sha256", "bytes", "used_by"], aud)
    print(f"tracking: {len(rows)} words, {len(ex)} examples, {sum(1 for r in rows if r['Conjugation'].strip())} conjugations, "
          f"{len(aud)} audio files ({missing} missing from {a.media}) -> {a.out}")
    if missing: sys.exit(1)


if __name__ == "__main__":
    main()
