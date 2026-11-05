#!/usr/bin/env python3
"""
Site-specific safety checks for catherinerbell.com.

Generic linters can't know this site's rules, so this script checks the
things that would either break the live site or break house style:

  1. House style: no em dashes, Enneagram "Points" never "Types".
  2. Every post has valid front matter and a correctly shaped filename.
  3. No post contains active content (script, iframe, inline event
     handlers, javascript: links). Posts are HTML, and some are AI-drafted.
  4. Load-bearing pieces are still in place: CNAME, Google Search Console
     verification tag, analytics, site URL.
  5. Nothing that looks like a credential is committed in tracked text files.
  6. If a built site exists (_site/), the feed and sitemap were generated.

Exit code 0 = all good. Exit code 1 = at least one problem; each problem is
printed as a GitHub annotation so it shows up on the PR's Files changed tab.

Run from the repo root:  python .github/scripts/content_guard.py
"""

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
problems = []


def fail(path, message, line=None):
    rel = path.relative_to(ROOT) if isinstance(path, pathlib.Path) else path
    loc = f"file={rel}" + (f",line={line}" if line else "")
    problems.append(f"::error {loc}::{message}")


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    # Include brand-new untracked posts (e.g. a fresh AI draft before commit).
    new_posts = [str(p.relative_to(ROOT)) for p in (ROOT / "_posts").glob("*.html")]
    return sorted({*out, *new_posts})


def visible_text(html):
    """Roughly the words a visitor reads: drop scripts, styles, tags."""
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def line_of(text, needle_index):
    return text.count("\n", 0, needle_index) + 1


CONTENT_GLOBS = ["*.html", "_posts/*.html", "_posts/*.md", "_includes/*.html", "_layouts/*.html"]
content_files = sorted({p for g in CONTENT_GLOBS for p in ROOT.glob(g)})

# ---- 1. House style -------------------------------------------------------
# Em dash or en dash used as punctuation. A lone dash as an element's whole
# content (the book countdown's dash placeholders, filled in by JS) is allowed.
DASH = re.compile(r"[\u2014\u2013]|&[mn]dash;|&#(8212|8211|x2014|x2013);", re.I)
PLACEHOLDER = re.compile(r">\s*([\u2014\u2013]|&[mn]dash;)\s*<", re.I)
TYPE_WORDS = re.compile(
    r"\b(Type\s+[1-9]|Types\s+[1-9]|Enneagram\s+types?|nine\s+types|"
    r"personality\s+types?)\b",
    re.I,
)

for f in content_files + [ROOT / "_config.yml"]:
    text = f.read_text(encoding="utf-8")
    scrubbed = PLACEHOLDER.sub("><", text)
    for m in DASH.finditer(scrubbed):
        fail(
            f,
            "Em/en dash found. House style: use a comma, colon, semicolon or parentheses instead.",
            line_of(scrubbed, m.start()),
        )
    if f.suffix == ".html":
        for m in TYPE_WORDS.finditer(visible_text(text)):
            fail(f, f'"{m.group(0)}": house style says Enneagram "Points", not "Types".')

# ---- 2 + 3. Posts ---------------------------------------------------------
POST_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.(html|md)$")
ACTIVE_CONTENT = [
    (re.compile(r"<\s*(script|iframe|object|embed|form|style)\b", re.I), "contains a <{0}> tag"),
    (re.compile(r"\son[a-z]+\s*=", re.I), "contains an inline event handler"),
    (re.compile(r"javascript\s*:", re.I), "contains a javascript: link"),
]

for f in sorted((ROOT / "_posts").glob("*")):
    if f.suffix not in {".html", ".md"}:
        continue
    if not POST_NAME.match(f.name):
        fail(f, "Post filename must look like YYYY-MM-DD-lowercase-slug.html")
    text = f.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fail(f, "Missing front matter block (--- ... ---) at top of post.")
        continue
    fm = m.group(1)
    for key in ("layout", "title", "author"):
        if not re.search(rf"^{key}:\s*\S", fm, re.M):
            fail(f, f"Front matter is missing '{key}:'.")
    title_line = re.search(r"^title:\s*(.*)$", fm, re.M)
    if title_line:
        t = title_line.group(1).strip()
        # Quoted titles must have balanced, escaped quotes or YAML breaks
        # and the whole site build fails.
        if t.startswith('"') and not re.fullmatch(r'"(?:[^"\\]|\\.)*"', t):
            fail(f, "Title has an unescaped double quote; this breaks the site build.")
    body = text[m.end() :]
    for pattern, msg in ACTIVE_CONTENT:
        hit = pattern.search(body)
        if hit:
            tag = hit.group(1) if hit.groups() else ""
            fail(
                f,
                "Post " + msg.format(tag) + ". Posts must be plain content (no scripts or embeds).",
                line_of(text, m.end() + hit.start()),
            )

# ---- 4. Load-bearing pieces -----------------------------------------------
cname = ROOT / "CNAME"
if not cname.exists() or cname.read_text().strip() != "catherinerbell.com":
    fail(
        cname, "CNAME must contain exactly 'catherinerbell.com' or the custom domain stops working."
    )

layout = (ROOT / "_layouts" / "default.html").read_text(encoding="utf-8")
if 'name="google-site-verification"' not in layout:
    fail(
        ROOT / "_layouts" / "default.html",
        "Google Search Console verification meta tag was removed.",
    )
if "plausible.io/js/" not in layout:
    fail(ROOT / "_layouts" / "default.html", "Plausible analytics script was removed.")

config = (ROOT / "_config.yml").read_text(encoding="utf-8")
if not re.search(r'^url:\s*"https://catherinerbell\.com"', config, re.M):
    fail(ROOT / "_config.yml", "Site url must stay https://catherinerbell.com")

# ---- 5. Credential-shaped strings -----------------------------------------
SECRET_PATTERNS = {
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "OpenAI API key": r"sk-(proj-)?[A-Za-z0-9]{32,}",
    "GitHub token": r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|github_pat_\w{40,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "Slack token": r"xox[abposr]-[A-Za-z0-9-]{10,}",
    "Mailchimp API key": r"\b[0-9a-f]{32}-us\d{1,2}\b",
    "Stripe secret key": r"sk_live_[A-Za-z0-9]{20,}",
    "Private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
BINARY = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2"}
for rel in tracked_files():
    p = ROOT / rel
    if p.suffix.lower() in BINARY or not p.is_file():
        continue
    if p.name.startswith(".env") and p.name != ".env.example":
        fail(p, ".env files must never be committed. Remove it and rotate any keys it contained.")
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for label, pat in SECRET_PATTERNS.items():
        for m in re.finditer(pat, text):
            fail(
                p,
                f"Looks like a committed {label}. Remove it, rotate the "
                "key, and store it as a GitHub secret instead.",
                line_of(text, m.start()),
            )

# ---- 6. Built output (only when _site exists) -----------------------------
site = ROOT / "_site"
if site.is_dir():
    for needed in (
        "index.html",
        "feed.xml",
        "sitemap.xml",
        "CNAME",
        "blog/index.html",
        "book/index.html",
        "contact/index.html",
    ):
        if not (site / needed).exists():
            fail(f"_site/{needed}", f"Built site is missing {needed}.")

if problems:
    print("\n".join(problems))
    print(f"\nContent guard: {len(problems)} problem(s) found.", file=sys.stderr)
    sys.exit(1)
print(f"Content guard: all checks passed ({len(content_files)} content files scanned).")
