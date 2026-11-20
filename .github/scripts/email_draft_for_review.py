#!/usr/bin/env python3
"""
Emails a new Ninth Moment draft to Catherine as an easy-to-read, branded
email (no GitHub links, nothing to log in to). She replies with edits or
"Approved"; the post only goes live when the draft PR is merged.

Run by the weekly workflow after the draft PR is opened:
    python .github/scripts/email_draft_for_review.py _posts/<file>.html

Preview without sending (writes the email HTML to a file):
    python .github/scripts/email_draft_for_review.py _posts/<file>.html --preview out.html

Settings (all kept out of the repo, so no addresses are public):
  SMTP_USERNAME      secret: the Google Workspace mailbox that sends (kent@...)
  SMTP_APP_PASSWORD  secret: a Google "app password" for that mailbox
  REVIEW_TO          variable: who reviews the draft (Catherine)
  REVIEW_CC          variable, optional: comma-separated copies (e.g. Kent)
"""

import html
import os
import pathlib
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr

PLUM = "#3a1f4d"
GOLD = "#c9a15a"
CREAM = "#faf6f2"
INK = "#241a2b"
INK_SOFT = "#5c4f66"
SERIF = "Fraunces, Georgia, 'Times New Roman', serif"
SANS = "Jost, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# Inline styles per tag: many email apps ignore <style> blocks.
TAG_STYLES = {
    "p": f"margin:0 0 18px;font-family:{SANS};font-size:17px;line-height:1.65;color:{INK};",
    "h2": f"margin:30px 0 12px;font-family:{SERIF};font-size:24px;line-height:1.25;"
    f"font-weight:600;color:{PLUM};",
    "h3": f"margin:24px 0 10px;font-family:{SERIF};font-size:20px;line-height:1.3;color:{PLUM};",
    "h4": f"margin:20px 0 8px;font-family:{SERIF};font-size:18px;color:{PLUM};",
    "blockquote": f"margin:0 0 18px;padding:4px 0 4px 18px;border-left:3px solid {GOLD};"
    f"font-style:italic;color:{INK_SOFT};",
    "ul": "margin:0 0 18px;padding-left:24px;",
    "ol": "margin:0 0 18px;padding-left:24px;",
    "li": f"margin:0 0 8px;font-family:{SANS};font-size:17px;line-height:1.6;color:{INK};",
    "a": f"color:{PLUM};text-decoration:underline;",
    "em": "",
    "strong": "",
    "b": "",
    "i": "",
    "br": "",
    "hr": f"border:0;border-top:1px solid {GOLD};margin:28px 0;",
    "span": "",
}


def read_post(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        sys.exit(f"ERROR: {path} has no front matter.")
    title = re.search(r'^title:\s*"?(.*?)"?\s*$', m.group(1), re.M)
    title = title.group(1).replace('\\"', '"') if title else "New blog draft"
    return title, m.group(2).strip()


def style_body(body):
    """Keep only allowed tags (the drafter already sanitized the post; this is
    a second line of defence) and give each one inline email styles."""

    def restyle(m):
        closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if name not in TAG_STYLES:
            return ""
        if closing:
            return f"</{name}>"
        style = f' style="{TAG_STYLES[name]}"' if TAG_STYLES[name] else ""
        if name == "a":
            href = re.search(r'href="(https://[^"]*|/[^"]*)"', attrs)
            if href:
                url = href.group(1)
                if url.startswith("/"):
                    url = "https://catherinerbell.com" + url
                return f'<a href="{html.escape(url, quote=True)}"{style}>'
            return "<a>"
        return f"<{name}{style}>"

    return re.sub(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>", restyle, body)


def plain_text(title, body):
    text = re.sub(r"</(p|h[2-4]|li|blockquote)>", "\n\n", body)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return (
        "Hi Catherine,\n\nHere is this week's blog draft for your review. Reply with any "
        'edits, or just "Approved". Nothing goes live until you approve it.\n\n'
        f"{title}\nBy The Ninth Moment\n\n{text}\n"
    )


FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:wght@400;600&family=Jost:wght@400;500&display=swap"
)
TABLE = 'role="presentation" width="100%" cellpadding="0" cellspacing="0"'
S_CARD = "max-width:640px;background:#ffffff;border-radius:14px;overflow:hidden;"
S_BRAND = f"font-family:{SERIF};font-size:20px;color:#ffffff;"
S_KICKER = (
    f"font-family:{SANS};font-size:12px;letter-spacing:2px;"
    f"text-transform:uppercase;color:{GOLD};margin-top:4px;"
)
S_NOTE = (
    f"background:{CREAM};border-left:4px solid {GOLD};border-radius:8px;"
    f"padding:14px 18px;font-family:{SANS};font-size:15px;"
    f"line-height:1.55;color:{INK_SOFT};"
)
S_TITLE = (
    f"margin:0 0 8px;font-family:{SERIF};font-size:32px;"
    f"line-height:1.2;font-weight:600;color:{PLUM};"
)
S_BYLINE = f"font-family:{SANS};font-size:14px;color:{INK_SOFT};margin-bottom:26px;"
S_FOOT = (
    f"background:{PLUM};padding:18px 32px;font-family:{SANS};"
    "font-size:12px;line-height:1.5;color:#e9defb;"
)
NOTE_TEXT = (
    "Hi Catherine, here is this week's draft. "
    f'<strong style="color:{PLUM};">Just reply to this email</strong> '
    'with any edits, or simply "Approved". Nothing goes live until you approve it.'
)
FOOT_TEXT = (
    "Draft for review only. Once approved it will be published on "
    "catherinerbell.com and sent to the Weekly Inspiration list."
)


def build_html(title, body):
    t = html.escape(title)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{t}</title>",
        f'<link href="{FONTS_URL}" rel="stylesheet">',
        "</head>",
        f'<body style="margin:0;padding:0;background:{CREAM};">',
        f'<table {TABLE} style="background:{CREAM};">',
        '<tr><td align="center" style="padding:24px 12px;">',
        f'<table {TABLE} style="{S_CARD}">',
        f'<tr><td style="background:{PLUM};padding:22px 32px;">',
        f'<div style="{S_BRAND}">Catherine R. Bell</div>',
        f'<div style="{S_KICKER}">Blog draft for your review</div>',
        "</td></tr>",
        '<tr><td style="padding:24px 32px 0;">',
        f'<div style="{S_NOTE}">{NOTE_TEXT}</div>',
        "</td></tr>",
        '<tr><td style="padding:28px 32px 8px;">',
        f'<h1 style="{S_TITLE}">{t}</h1>',
        f'<div style="{S_BYLINE}">By The Ninth Moment</div>',
        style_body(body),
        "</td></tr>",
        f'<tr><td style="{S_FOOT}">{FOOT_TEXT}</td></tr>',
        "</table>",
        "</td></tr></table>",
        "</body></html>",
        "",
    ]
    return "\n".join(parts)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: email_draft_for_review.py _posts/<file>.html [--preview out.html]")
    title, body = read_post(args[0])
    page = build_html(title, body)

    if len(args) == 3 and args[1] == "--preview":
        pathlib.Path(args[2]).write_text(page, encoding="utf-8")
        print(f"Preview written to {args[2]}")
        return

    user = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", "")
    to = os.environ.get("REVIEW_TO", "").strip()
    cc = [a.strip() for a in os.environ.get("REVIEW_CC", "").split(",") if a.strip()]
    if not (user and password and to):
        sys.exit(
            "ERROR: SMTP_USERNAME, SMTP_APP_PASSWORD (secrets) and REVIEW_TO (variable) "
            "must be set in the ninth-moment environment. The draft PR is open; "
            "send the draft manually this week."
        )

    msg = EmailMessage()
    # EmailMessage refuses header values containing newlines, so an odd
    # title cannot inject extra headers.
    msg["Subject"] = f"Blog draft for your review: {title}"
    msg["From"] = formataddr(("Catherine R. Bell website", user))
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Reply-To"] = user
    msg.set_content(plain_text(title, body))
    msg.add_alternative(page, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, password)
        s.send_message(msg)
    print("Review email sent.")


if __name__ == "__main__":
    main()
