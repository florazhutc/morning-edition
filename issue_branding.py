import re
from datetime import datetime
from pathlib import Path


MOUNTAIN_MARK = '''
<svg aria-hidden="true" viewBox="0 0 64 42" fill="none">
    <path d="M4 38 24 4l8 14 7-10 21 30H4Z" fill="currentColor"></path>
    <path d="M28 38c5-9 11-14 18-19-4 1-8 0-11-3 2 7 0 14-7 22Z" fill="var(--warm-white)"></path>
    <path d="m23 19 4-7 4 8m13 0 3-5 5 7" stroke="var(--warm-white)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path>
</svg>
'''


def issue_details(path, number):
    date = datetime.strptime(path.stem, "%Y-%m-%d")
    return {
        "filename": path.name,
        "date_iso": path.stem,
        "display_date": date.strftime("%B %d, %Y"),
        "day_name": date.strftime("%A"),
        "number": number,
    }


def render_issue_header(issue):
    return f'''<!-- ISSUE HEADER START -->
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <header class="issue-site-header">
        <div class="issue-shell issue-header-inner">
            <a class="issue-brand" href="https://wildernesstudio.com/" target="_blank" rel="noopener" aria-label="Visit Wilderness Studio">
                {MOUNTAIN_MARK}
                <span class="issue-wordmark"><span>Wilderness</span><span>Studio</span></span>
            </a>
            <nav class="issue-header-nav" aria-label="Issue navigation">
                <a href="../index.html">Issue archive</a>
                <a href="#toc">In this issue</a>
            </nav>
        </div>
    </header>
    <main id="main-content">
        <section class="issue-hero" aria-labelledby="issue-title">
            <div class="issue-shell issue-hero-layout">
                <div>
                    <p class="issue-kicker">A Wilderness Studio product · Issue {issue['number']:03d}</p>
                    <h1 id="issue-title"><span>HN</span><span>Daily Brief</span></h1>
                    <svg class="issue-stroke" viewBox="0 0 320 28" preserveAspectRatio="none" aria-hidden="true"><path d="M5 18 C74 5 148 24 226 12 C264 6 291 8 315 5"></path></svg>
                </div>
                <div class="issue-date-block">
                    <span>{issue['day_name']}</span>
                    <time datetime="{issue['date_iso']}">{issue['display_date']}</time>
                    <p>Curated Hacker News signals for AI-native builders.</p>
                </div>
            </div>
        </section>
<!-- ISSUE HEADER END -->'''


def render_issue_link(label, issue, direction):
    if not issue:
        edge_label = "Start of archive" if direction == "previous" else "Latest published issue"
        return f'<span class="issue-nav-link is-disabled"><small>{label}</small><strong>{edge_label}</strong></span>'

    arrow = "←" if direction == "previous" else "→"
    return f'''<a class="issue-nav-link" href="{issue['filename']}">
        <small>{label}</small>
        <strong>{arrow} {issue['display_date']}</strong>
    </a>'''


def render_issue_footer(issue, previous_issue, next_issue):
    return f'''<!-- ISSUE FOOTER START -->
    </main>
    <nav class="edition-navigation issue-shell" aria-label="Previous and next issues">
        {render_issue_link("Previous issue", previous_issue, "previous")}
        {render_issue_link("Next issue", next_issue, "next")}
    </nav>
    <footer class="issue-footer">
        <div class="issue-shell issue-footer-inner">
            <div>
                <div class="issue-footer-brand">{MOUNTAIN_MARK}<span>Wilderness Studio</span></div>
                <p>HN Daily Brief · Curated daily intelligence for AI-native builders.</p>
            </div>
            <div class="issue-footer-signature">
                <strong>Experience leads. AI amplifies.</strong>
                <a href="https://wildernesstudio.com/" target="_blank" rel="noopener">wildernesstudio.com ↗</a>
            </div>
        </div>
    </footer>
<!-- ISSUE FOOTER END -->'''


def normalize_legacy_english(html):
    html = re.sub(
        r'<(?:div|h3|p)\b[^>]*font-family:\s*["\']Noto (?:Serif|Sans) SC["\'][^>]*>.*?</(?:div|h3|p)>',
        "",
        html,
        flags=re.DOTALL,
    )
    replacements = {
        "In This Issue / 本期提要": "In This Issue",
        "HIGHLY RELEVANT TO YOU / 高度相关": "HIGHLY RELEVANT",
        "Actionable Insight / 洞察与行动": "Actionable Insight",
        "Community Voice / 社区声音": "Community Voice",
        "Read Source / 阅读原稿": "Read Source",
        "HN Discussion / HN 讨论": "HN Discussion",
        "HN Discussion / 参与讨论": "HN Discussion",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    html = re.sub(r'🔥\s*(\d+)\s*热度', r'\1 pts', html)
    html = re.sub(r'(&nbsp;)?\|(&nbsp;)?\s*[^<]*[\u3400-\u9fff][^<]*', "", html)
    html = re.sub(
        r'<div class="toc-header">\s*In This Issue\s*</div>',
        '<h2 class="toc-header" id="toc-title">In This Issue</h2>',
        html,
    )
    html = re.sub(
        r'<span([^>]*)>\s*In This Issue\s*</span>',
        r'<h2 id="toc-title"\1>In This Issue</h2>',
        html,
        count=1,
    )
    html = html.replace('<div class="toc" id="toc">', '<div class="toc" id="toc" aria-labelledby="toc-title">', 1)
    return html


def update_issue_page(path, issue, previous_issue, next_issue):
    html = path.read_text(encoding="utf-8")
    html = normalize_legacy_english(html)
    html = re.sub(
        r"<title>.*?</title>",
        f"<title>HN Daily Brief — {issue['display_date']}</title>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    if 'name="description"' not in html:
        description = (
            f'    <meta name="description" content="HN Daily Brief issue {issue["number"]:03d}, '
            f'{issue["display_date"]}: curated Hacker News signals for AI-native builders.">\n'
        )
        html = html.replace("    <title>", description + "    <title>", 1)

    stylesheet = '    <link rel="stylesheet" href="../assets/issue.css">\n'
    if '../assets/issue.css' not in html:
        html = html.replace("</head>", stylesheet + "</head>", 1)

    header = render_issue_header(issue)
    if "<!-- ISSUE HEADER START -->" in html:
        html = re.sub(
            r"<!-- ISSUE HEADER START -->.*?<!-- ISSUE HEADER END -->",
            header,
            html,
            count=1,
            flags=re.DOTALL,
        )
    else:
        html = re.sub(
            r"<!-- FLOATING ACTION BAR -->.*?(?=<!-- TABLE OF CONTENTS -->)",
            header + "\n\n    ",
            html,
            count=1,
            flags=re.DOTALL,
        )

    footer = render_issue_footer(issue, previous_issue, next_issue)
    if "<!-- ISSUE FOOTER START -->" in html:
        html = re.sub(
            r"<!-- ISSUE FOOTER START -->.*?<!-- ISSUE FOOTER END -->",
            footer,
            html,
            count=1,
            flags=re.DOTALL,
        )
    else:
        html = re.sub(
            r"<!-- COLOPHON -->.*?(?=</body>)",
            footer + "\n",
            html,
            count=1,
            flags=re.DOTALL,
        )

    html = html.replace("    </style>\n    </style>", "    </style>")
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    path.write_text(html, encoding="utf-8")


def update_issue_pages(magazines_dir=Path("magazines")):
    paths = sorted(magazines_dir.glob("*.html"))
    issues = [issue_details(path, number) for number, path in enumerate(paths, start=1)]
    for index, (path, issue) in enumerate(zip(paths, issues)):
        previous_issue = issues[index - 1] if index > 0 else None
        next_issue = issues[index + 1] if index + 1 < len(issues) else None
        update_issue_page(path, issue, previous_issue, next_issue)
    return len(issues)
