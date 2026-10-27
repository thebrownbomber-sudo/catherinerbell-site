#!/usr/bin/env python3
"""
Drafts a new "Ninth Moment" blog post for catherinerbell.com and writes it
as a new file under _posts/, in the exact front-matter format the Jekyll
site expects. Run from the repo root inside the weekly GitHub Action.

Does NOT commit, push, or open a PR -- the workflow file handles that after
this script exits successfully. This script's only job is to produce one
valid _posts/YYYY-MM-DD-slug.html file, or fail loudly and write nothing.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
POSTS_DIR = REPO_ROOT / "_posts"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
# Override via the ANTHROPIC_MODEL repo variable if this ever needs to change.
# Check console.anthropic.com for the current list of available model IDs.
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY is not set. Add it as a repo secret "
          "(Settings -> Secrets and variables -> Actions).", file=sys.stderr)
    sys.exit(1)


def load_existing_posts():
    """Read every existing post's front matter so the draft doesn't repeat
    a topic and can continue the established throughline naturally."""
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for f in sorted(POSTS_DIR.glob("*.html")):
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.S)
        if not m:
            continue
        front_matter_raw, body = m.group(1), m.group(2)
        fm = {}
        for line in front_matter_raw.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
        posts.append({
            "filename": f.name,
            "title": fm.get("title", ""),
            "author": fm.get("author", ""),
            "ai_drafted": fm.get("ai_drafted", "false"),
            # first ~400 chars of body, stripped of tags, just for context
            "excerpt": re.sub(r"<[^>]+>", " ", body)[:400].strip(),
        })
    return posts


STYLE_GUIDE = """\
You are "The Ninth Moment," an AI-drafted contributor to catherinerbell.com, \
the website of Catherine R. Bell -- Enneagram and executive coach, keynote \
speaker, and co-author of "The Creative Moment: Awaken Creativity Through \
the Enneagram" (with Russ Hudson, Penguin Random House, May 2027).

Write ONE new blog post for the site's Blog section. Follow these rules \
exactly, without exception:

HOUSE STYLE
- Never use an em dash anywhere in the text. Use commas, colons, \
  semicolons, or parentheses instead.
- Always refer to Enneagram "Points," never "Types" (e.g. "Point 4," \
  "the nine Points," never "Type 4" or "personality type").
- Write in a reflective, essayistic register: substantive and specific, \
  not generic self-help language. Avoid cliche phrases like "unlock your \
  potential" or "journey of self-discovery."
- Second person ("you") is fine where it earns its place, but the piece \
  should read like genuine thinking, not a listicle or a sales page.
- Do not end with a cheesy call-to-action or "so what will you choose?" \
  closer. End when the thought is actually finished.
- Target length: 900 to 1400 words.
- The piece should continue the blog's established throughline (Points, \
  then the three Centers of Body/Heart/Head, then what remains uniquely \
  human in creativity versus what a machine can do) in a way that feels \
  like a natural next entry, not a rehash. You do not have to mention \
  AI/machines in every post, but the throughline should feel continuous \
  with what has already been published, not disconnected from it.

OUTPUT FORMAT
Respond with ONLY a JSON object, no other text before or after it, with \
exactly these two keys:
{
  "title": "the post's title, as plain text, no surrounding quotes",
  "body_html": "the full post body as HTML, using <p> tags for paragraphs \
and <h2> for any subheadings if used. Do not include the title itself in \
the body, do not include a byline, do not include a date -- the site \
template adds those automatically. Do not wrap the body in <article> or \
<body> tags, just the inner content."
}
"""


def build_user_prompt(existing_posts):
    lines = [
        "Here are the posts already published on the blog, most recent "
        "first, so you can avoid repeating a topic and can continue the "
        "throughline naturally:\n",
    ]
    for p in reversed(existing_posts):
        lines.append(
            f"- \"{p['title']}\" (by {p['author'] or 'unknown'}): "
            f"{p['excerpt']}..."
        )
    lines.append(
        "\nWrite the next post in this series now. Pick whatever specific "
        "angle feels like the genuine next step in the throughline, not "
        "necessarily a mechanical continuation."
    )
    return "\n".join(lines)


def call_claude(system_prompt, user_prompt):
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"]


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s[:60].rstrip("-")


def main():
    existing_posts = load_existing_posts()
    user_prompt = build_user_prompt(existing_posts)

    raw = call_claude(STYLE_GUIDE, user_prompt)

    # The model should return pure JSON per the style guide, but strip any
    # accidental code-fence wrapping defensively before parsing.
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"ERROR: model did not return valid JSON: {e}", file=sys.stderr)
        print(f"Raw output was:\n{raw}", file=sys.stderr)
        sys.exit(1)

    title = parsed.get("title", "").strip()
    body_html = parsed.get("body_html", "").strip()

    if not title or len(body_html) < 400:
        print("ERROR: draft failed basic validation (missing title or "
              "body too short). Refusing to write a file.", file=sys.stderr)
        sys.exit(1)

    today = datetime.date.today()
    slug = slugify(title)
    if not slug:
        print("ERROR: could not derive a usable slug from the title.",
              file=sys.stderr)
        sys.exit(1)

    filename = f"{today.isoformat()}-{slug}.html"
    out_path = POSTS_DIR / filename

    front_matter = (
        "---\n"
        "layout: post\n"
        f'title: "{title}"\n'
        'author: "The Ninth Moment"\n'
        "ai_drafted: true\n"
        "---\n\n"
    )
    out_path.write_text(front_matter + body_html + "\n", encoding="utf-8")

    print(f"Wrote draft: {out_path}")
    # Emit the title and filename for the workflow to use in the PR.
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"post_title={title}\n")
            f.write(f"post_filename={filename}\n")


if __name__ == "__main__":
    main()
