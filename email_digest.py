from datetime import datetime
from html import escape, unescape
import re


WARM_WHITE = "#F8F4EC"
SAND = "#E5DED2"
DEEP_FOREST = "#073D2D"
BUILDER_YELLOW = "#F5B82E"
MUTED_GRAY = "#62625C"
WHITE = "#FFFEFB"


def build_issue_url(site_url, date_str):
    return f"{site_url.rstrip('/')}/magazines/{date_str}.html"


def format_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return date_str


def compact_text(value, limit=220):
    text = re.sub(r"\s+", " ", unescape(str(value or ""))).strip()
    if len(text) <= limit:
        return text
    shortened = text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;: ")
    return f"{shortened}…"


def render_story_row(story, index):
    title = escape(str(story.get("title", "Untitled")), quote=True)
    url = escape(str(story.get("url", "")), quote=True)
    hn_url = escape(str(story.get("hn_url", "")), quote=True)
    domain = escape(str(story.get("domain", "Hacker News")), quote=True)
    category = escape(str(story.get("insight_cat_en", "Daily signal")), quote=True)
    summary = escape(compact_text(story.get("summary_en", "")), quote=True)
    score = escape(str(story.get("score", 0)), quote=True)
    priority = " · Priority signal" if story.get("flagged") else ""

    if summary:
        summary_html = f'''<p style="margin:12px 0 0;color:{MUTED_GRAY};font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;">{summary}</p>'''
    else:
        summary_html = ""

    return f'''
                <tr>
                    <td width="42" valign="top" style="width:42px;padding:24px 12px 24px 0;color:{DEEP_FOREST};font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.4;">{index:02d}</td>
                    <td valign="top" style="padding:24px 0;">
                        <div style="margin:0 0 8px;color:#52634A;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;letter-spacing:1.2px;line-height:1.4;text-transform:uppercase;">{category}{priority}</div>
                        <a href="{url}" style="color:{DEEP_FOREST};font-family:Georgia,'Times New Roman',serif;font-size:24px;font-weight:bold;line-height:1.25;text-decoration:none;">{title}</a>
                        <div style="margin-top:9px;color:{MUTED_GRAY};font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;">{domain} · {score} pts</div>
                        {summary_html}
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin-top:15px;">
                            <tr>
                                <td style="padding-right:18px;"><a href="{url}" style="color:{DEEP_FOREST};font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;text-decoration:underline;text-decoration-color:{BUILDER_YELLOW};">Read source →</a></td>
                                <td><a href="{hn_url}" style="color:{DEEP_FOREST};font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;text-decoration:underline;text-decoration-color:{BUILDER_YELLOW};">HN discussion →</a></td>
                            </tr>
                        </table>
                    </td>
                </tr>
                <tr><td colspan="2" height="1" bgcolor="{SAND}" style="height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>'''


def render_email_digest(stories, date_str, issue_url):
    display_date = format_date(date_str)
    safe_issue_url = escape(issue_url, quote=True)
    story_rows = "".join(render_story_row(story, index) for index, story in enumerate(stories, start=1))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HN Daily Brief — {display_date}</title>
</head>
<body style="margin:0;padding:0;background-color:{WARM_WHITE};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">Today's Hacker News signals for AI-native builders.</div>
    <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="{WARM_WHITE}" style="width:100%;background-color:{WARM_WHITE};">
        <tr>
            <td align="center" style="padding:0 12px;">
                <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;">
                    <tr><td height="5" bgcolor="{BUILDER_YELLOW}" style="height:5px;font-size:0;line-height:0;">&nbsp;</td></tr>
                    <tr>
                        <td bgcolor="{DEEP_FOREST}" style="padding:34px 28px 38px;background-color:{DEEP_FOREST};">
                            <div style="color:{BUILDER_YELLOW};font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;letter-spacing:2px;line-height:1.5;text-transform:uppercase;">Wilderness Studio · Daily intelligence</div>
                            <h1 style="margin:18px 0 0;color:{WHITE};font-family:Georgia,'Times New Roman',serif;font-size:42px;line-height:1.05;">HN Daily Brief</h1>
                            <div style="margin-top:12px;color:{BUILDER_YELLOW};font-family:Georgia,'Times New Roman',serif;font-size:21px;line-height:1.4;">{display_date}</div>
                            <p style="margin:18px 0 0;color:#DDE9E4;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;">Curated Hacker News signals for AI-native builders, product thinkers, and creative technologists.</p>
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin-top:24px;">
                                <tr>
                                    <td bgcolor="{BUILDER_YELLOW}" style="background-color:{BUILDER_YELLOW};border-radius:999px;">
                                        <a href="{safe_issue_url}" style="display:inline-block;padding:13px 22px;color:{DEEP_FOREST};font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:bold;text-decoration:none;">Read the full issue →</a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:28px 24px 8px;">
                            <div style="color:#52634A;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:bold;letter-spacing:2px;line-height:1.5;text-transform:uppercase;">In this issue</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:0 24px 24px;">
                            <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="width:100%;">
                                {story_rows}
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align="center" bgcolor="{DEEP_FOREST}" style="padding:30px 24px;background-color:{DEEP_FOREST};">
                            <div style="color:{WHITE};font-family:Georgia,'Times New Roman',serif;font-size:22px;font-style:italic;line-height:1.4;">Experience leads. AI amplifies.</div>
                            <p style="margin:10px 0 18px;color:#DDE9E4;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;">HN Daily Brief is a Wilderness Studio product.</p>
                            <a href="{safe_issue_url}" style="color:{BUILDER_YELLOW};font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:bold;text-decoration:underline;">View this issue online →</a>
                        </td>
                    </tr>
                    <tr><td height="28" style="height:28px;font-size:0;line-height:0;">&nbsp;</td></tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''


def render_email_text(stories, date_str, issue_url):
    lines = [
        f"HN DAILY BRIEF — {format_date(date_str)}",
        "A Wilderness Studio product",
        "",
        f"Read the full issue: {issue_url}",
        "",
        "IN THIS ISSUE",
    ]
    for index, story in enumerate(stories, start=1):
        lines.extend(
            [
                "",
                f"{index:02d}. {compact_text(story.get('title', 'Untitled'), 140)}",
                f"{story.get('domain', 'Hacker News')} · {story.get('score', 0)} pts",
            ]
        )
        summary = compact_text(story.get("summary_en", ""))
        if summary:
            lines.append(summary)
        lines.append(f"Source: {story.get('url', '')}")
        lines.append(f"Discussion: {story.get('hn_url', '')}")
    lines.extend(["", "Experience leads. AI amplifies.", "https://wildernesstudio.com/"])
    return "\n".join(lines) + "\n"
