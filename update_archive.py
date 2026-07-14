from datetime import datetime
from pathlib import Path

from issue_branding import MOUNTAIN_MARK, update_issue_pages


def build_issue(path, issue_number):
    date_str = path.stem
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        date = None

    return {
        "filename": path.name,
        "date_iso": date_str,
        "display_date": date.strftime("%B %d, %Y") if date else date_str,
        "short_date": date.strftime("%B %d") if date else date_str,
        "month": date.strftime("%B %Y") if date else "Other Issues",
        "month_short": date.strftime("%b").upper() if date else "ISSUE",
        "day": date.strftime("%d") if date else "--",
        "year": date.strftime("%Y") if date else "",
        "number": issue_number,
    }


def render_issue_card(issue, color_class):
    number = f"{issue['number']:03d}"
    return f'''
        <a href="magazines/{issue['filename']}" class="issue-card {color_class}" aria-label="Read HN Daily Brief issue {number}, {issue['display_date']}">
            <div class="issue-card-meta">
                <span>Issue {number}</span>
                <time datetime="{issue['date_iso']}">{issue['short_date']}</time>
            </div>
            <div class="issue-card-body">
                <span class="issue-card-title">HN Daily Brief</span>
                <span class="issue-card-arrow" aria-hidden="true">Read issue <span>↗</span></span>
            </div>
        </a>
    '''


def render_archive_groups(issues):
    groups = {}
    for issue in issues:
        groups.setdefault(issue["month"], []).append(issue)

    color_classes = ["card-warm", "card-mint", "card-blue", "card-peach", "card-lilac"]
    sections = []
    card_index = 0
    for month, month_issues in groups.items():
        cards = []
        for issue in month_issues:
            cards.append(render_issue_card(issue, color_classes[card_index % len(color_classes)]))
            card_index += 1
        sections.append(f'''
        <section class="month-group" aria-labelledby="month-{card_index}">
            <div class="month-heading">
                <h3 id="month-{card_index}">{month}</h3>
                <span>{len(month_issues)} {"issue" if len(month_issues) == 1 else "issues"}</span>
            </div>
            <div class="archive-grid">
                {"".join(cards)}
            </div>
        </section>
        ''')
    return "".join(sections)


def generate_index():
    magazines_dir = Path("magazines")
    if not magazines_dir.exists():
        print(f"Directory {magazines_dir} does not exist.")
        return

    paths = sorted(magazines_dir.glob("*.html"))
    numbered = [build_issue(path, index) for index, path in enumerate(paths, start=1)]
    issues = list(reversed(numbered))
    latest = issues[0] if issues else None
    previous_issues = issues[1:]

    if latest:
        latest_number = f"{latest['number']:03d}"
        latest_html = f'''
        <a href="magazines/{latest['filename']}" class="latest-card" aria-label="Read latest HN Daily Brief, {latest['display_date']}">
            <div class="latest-card-topline">
                <span class="latest-label"><span aria-hidden="true"></span> Latest issue</span>
                <span>Issue {latest_number}</span>
            </div>
            <div class="latest-card-layout">
                <time class="latest-date" datetime="{latest['date_iso']}">
                    <span>{latest['month_short']}</span>
                    <strong>{latest['day']}</strong>
                    <span>{latest['year']}</span>
                </time>
                <div class="latest-copy">
                    <h2>Today’s signals,<br>selected with judgment.</h2>
                    <p>The latest Hacker News stories for AI-native builders, product thinkers, and creative technologists.</p>
                    <span class="latest-cta">Read latest brief <span aria-hidden="true">→</span></span>
                </div>
            </div>
            <span class="latest-orbit" aria-hidden="true"></span>
            <span class="latest-dots" aria-hidden="true"></span>
        </a>
        '''
    else:
        latest_html = '<div class="empty-state">No issues found yet. Check back tomorrow.</div>'

    archive_html = render_archive_groups(previous_issues)
    issue_count = len(issues)

    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="HN Daily Brief is a curated daily intelligence product from Wilderness Studio for AI-native builders.">
    <title>HN Daily Brief · A Wilderness Studio Product</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --font-display: "Iowan Old Style", "Palatino Linotype", "Songti SC", "Noto Serif CJK SC", Georgia, serif;
            --font-sans: Inter, "Helvetica Neue", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
            --warm-white: #F8F4EC;
            --sand: #E5DED2;
            --deep-forest: #073D2D;
            --builder-yellow: #F5B82E;
            --soft-olive: #8A9A7B;
            --soft-mint: #DDEFE5;
            --soft-peach: #F6D7C8;
            --lilac-mist: #E6DDF7;
            --mist-blue: #D6EAF7;
            --charcoal: #121212;
            --muted-gray: #62625C;
            --border: #E5DED2;
            --white: #FFFEFB;
            --shadow-sm: 0 10px 30px rgba(18, 18, 18, 0.055);
            --shadow-lg: 0 22px 60px rgba(7, 61, 45, 0.13);
        }}

        * {{ box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
            margin: 0;
            background:
                radial-gradient(circle at 88% 8%, rgba(245, 184, 46, 0.16), transparent 20rem),
                linear-gradient(135deg, var(--warm-white) 0%, var(--warm-white) 58%, #F2E9DB 100%);
            color: var(--charcoal);
            font-family: var(--font-sans);
            line-height: 1.6;
            text-rendering: optimizeLegibility;
            -webkit-font-smoothing: antialiased;
        }}
        a {{ color: inherit; }}
        .skip-link {{
            position: fixed; left: 1rem; top: 1rem; z-index: 100;
            padding: 0.75rem 1rem; border-radius: 999px;
            background: var(--builder-yellow); color: var(--deep-forest);
            font-weight: 700; transform: translateY(-200%);
        }}
        .skip-link:focus {{ transform: translateY(0); }}
        a:focus-visible {{ outline: 3px solid var(--builder-yellow); outline-offset: 4px; }}
        .shell {{ width: min(100% - 2.5rem, 80rem); margin-inline: auto; }}

        .site-header {{
            position: sticky; top: 0; z-index: 20;
            border-bottom: 1px solid rgba(229, 222, 210, 0.85);
            background: rgba(248, 244, 236, 0.88);
            backdrop-filter: blur(18px);
        }}
        .site-header-inner {{ min-height: 5rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
        .brand-lockup {{ display: inline-flex; align-items: center; gap: 0.75rem; color: var(--deep-forest); text-decoration: none; }}
        .brand-lockup svg {{ width: 3rem; height: 2rem; flex: 0 0 auto; }}
        .brand-wordmark {{ display: grid; line-height: 1; text-transform: uppercase; font-weight: 700; }}
        .brand-wordmark span:first-child {{ font-size: 0.78rem; letter-spacing: 0.25em; }}
        .brand-wordmark span:last-child {{ margin-top: 0.32rem; font-size: 0.64rem; letter-spacing: 0.46em; }}
        .studio-link {{
            min-height: 2.75rem; display: inline-flex; align-items: center;
            padding: 0.55rem 1rem; border: 1px solid rgba(7, 61, 45, 0.35);
            border-radius: 999px; color: var(--deep-forest); text-decoration: none;
            font-size: 0.78rem; font-weight: 700; transition: 180ms ease;
        }}
        .studio-link:hover {{ background: var(--builder-yellow); border-color: var(--builder-yellow); transform: translateY(-2px); }}

        .hero {{
            min-height: 38rem; display: grid; grid-template-columns: minmax(0, 0.88fr) minmax(26rem, 1.12fr);
            align-items: center; gap: clamp(2.5rem, 7vw, 7rem); padding-block: clamp(4rem, 8vw, 7.5rem);
        }}
        .product-label {{
            display: inline-flex; align-items: center; gap: 0.6rem;
            color: var(--soft-olive); font-size: 0.72rem; font-weight: 700;
            letter-spacing: 0.22em; text-transform: uppercase;
        }}
        .product-label::before {{ content: ""; width: 1.75rem; height: 2px; background: var(--builder-yellow); }}
        h1 {{ margin: 1.5rem 0 0; color: var(--deep-forest); font-family: var(--font-display); font-weight: 600; line-height: 0.82; letter-spacing: -0.055em; }}
        h1 span {{ display: block; }}
        h1 span:first-child {{ font-family: var(--font-sans); font-size: clamp(2rem, 5vw, 4.3rem); font-weight: 700; letter-spacing: 0.12em; line-height: 1; }}
        h1 span:last-child {{ font-size: clamp(4rem, 6.6vw, 6.4rem); white-space: nowrap; }}
        .brand-stroke {{ display: block; width: min(23rem, 82%); height: 2rem; margin-top: 0.7rem; }}
        .brand-stroke path {{ fill: none; stroke: var(--builder-yellow); stroke-width: 5; stroke-linecap: round; }}
        .hero-description {{ max-width: 34rem; margin: 1.5rem 0 0; color: var(--muted-gray); font-size: clamp(1rem, 1.8vw, 1.18rem); line-height: 1.8; }}
        .hero-meta {{ margin-top: 1.5rem; color: var(--deep-forest); font-size: 0.78rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }}
        .hero-tags {{ display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 1.75rem; }}
        .hero-tags span {{ padding: 0.45rem 0.75rem; border: 1px solid var(--border); border-radius: 999px; background: rgba(255,255,255,0.55); color: var(--deep-forest); font-size: 0.66rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}

        .latest-card {{
            position: relative; display: block; min-height: 29rem; overflow: hidden;
            padding: clamp(1.5rem, 4vw, 2.6rem); border-radius: 1.5rem;
            background: linear-gradient(135deg, #073D2D 0%, #0D4B3D 100%);
            color: var(--white); text-decoration: none; box-shadow: var(--shadow-lg);
            transition: transform 250ms ease, box-shadow 250ms ease;
            isolation: isolate;
        }}
        .latest-card:hover {{ transform: translateY(-5px); box-shadow: 0 30px 72px rgba(7, 61, 45, 0.2); }}
        .latest-card-topline {{ position: relative; z-index: 2; display: flex; justify-content: space-between; gap: 1rem; color: rgba(255,255,255,0.68); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }}
        .latest-label {{ display: inline-flex; align-items: center; gap: 0.55rem; color: var(--builder-yellow); }}
        .latest-label > span {{ width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--builder-yellow); box-shadow: 0 0 0 5px rgba(245,184,46,0.12); }}
        .latest-card-layout {{ position: relative; z-index: 2; display: grid; grid-template-columns: 7rem 1fr; align-items: end; gap: 2.25rem; min-height: 22rem; padding-top: 3.25rem; }}
        .latest-date {{ display: grid; align-content: end; color: var(--builder-yellow); text-align: center; font-weight: 700; letter-spacing: 0.14em; }}
        .latest-date strong {{ font-family: var(--font-display); font-size: 6.5rem; font-weight: 600; line-height: 0.8; letter-spacing: -0.08em; }}
        .latest-date span {{ font-size: 0.72rem; }}
        .latest-copy h2 {{ margin: 0; font-family: var(--font-display); font-size: clamp(2rem, 4vw, 3.25rem); font-weight: 600; line-height: 1.03; letter-spacing: -0.035em; }}
        .latest-copy p {{ max-width: 27rem; margin: 1.25rem 0 0; color: rgba(255,255,255,0.7); font-size: 0.91rem; line-height: 1.75; }}
        .latest-cta {{ display: inline-flex; align-items: center; gap: 0.8rem; min-height: 2.8rem; margin-top: 1.6rem; padding: 0.35rem 1.1rem; border-radius: 999px; background: var(--builder-yellow); color: var(--deep-forest); font-size: 0.78rem; font-weight: 700; }}
        .latest-cta span {{ font-size: 1.05rem; transition: transform 180ms ease; }}
        .latest-card:hover .latest-cta span {{ transform: translateX(4px); }}
        .latest-orbit {{ position: absolute; right: -5rem; top: 3.5rem; width: 15rem; height: 15rem; border: 1px solid rgba(245,184,46,0.2); border-radius: 50%; box-shadow: 0 0 0 2.6rem rgba(245,184,46,0.025), 0 0 0 5.2rem rgba(245,184,46,0.02); }}
        .latest-dots {{ position: absolute; right: 2.5rem; top: 7rem; width: 6rem; height: 6rem; opacity: 0.22; background-image: radial-gradient(var(--builder-yellow) 1.2px, transparent 1.2px); background-size: 12px 12px; }}

        main {{ padding-bottom: clamp(5rem, 9vw, 8rem); }}
        .archive-section {{ border-top: 1px solid var(--border); padding-top: clamp(4rem, 8vw, 7rem); }}
        .archive-header {{ display: grid; grid-template-columns: 1fr auto; align-items: end; gap: 2rem; margin-bottom: 4rem; }}
        .archive-eyebrow {{ margin: 0 0 0.65rem; color: var(--soft-olive); font-size: 0.7rem; font-weight: 700; letter-spacing: 0.22em; text-transform: uppercase; }}
        .archive-header h2 {{ margin: 0; color: var(--deep-forest); font-family: var(--font-display); font-size: clamp(2.7rem, 5vw, 4.8rem); font-weight: 600; line-height: 1; letter-spacing: -0.04em; }}
        .archive-count {{ color: var(--muted-gray); font-size: 0.76rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }}
        .month-group + .month-group {{ margin-top: 4.5rem; }}
        .month-heading {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }}
        .month-heading h3 {{ margin: 0; color: var(--deep-forest); font-size: 0.74rem; font-weight: 700; letter-spacing: 0.22em; text-transform: uppercase; }}
        .month-heading span {{ color: var(--muted-gray); font-size: 0.7rem; }}
        .archive-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; margin-top: 1rem; }}
        .issue-card {{
            min-height: 10.5rem; display: flex; flex-direction: column; justify-content: space-between;
            padding: 1.35rem 1.5rem; border: 1px solid var(--border); border-radius: 1.2rem;
            color: var(--deep-forest); text-decoration: none; box-shadow: var(--shadow-sm);
            transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
        }}
        .issue-card:hover {{ transform: translateY(-4px); border-color: rgba(7,61,45,0.34); box-shadow: 0 18px 42px rgba(18,18,18,0.08); }}
        .card-warm {{ background: rgba(255,254,251,0.84); }}
        .card-mint {{ background: rgba(221,239,229,0.7); }}
        .card-blue {{ background: rgba(214,234,247,0.66); }}
        .card-peach {{ background: rgba(246,215,200,0.6); }}
        .card-lilac {{ background: rgba(230,221,247,0.58); }}
        .issue-card-meta {{ display: flex; justify-content: space-between; gap: 1rem; color: rgba(7,61,45,0.68); font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }}
        .issue-card-body {{ display: flex; align-items: end; justify-content: space-between; gap: 1rem; }}
        .issue-card-title {{ font-family: var(--font-display); font-size: clamp(1.55rem, 3vw, 2.15rem); font-weight: 600; line-height: 1; letter-spacing: -0.025em; }}
        .issue-card-arrow {{ display: inline-flex; align-items: center; gap: 0.45rem; white-space: nowrap; font-size: 0.7rem; font-weight: 700; }}
        .issue-card-arrow span {{ font-size: 1rem; transition: transform 180ms ease; }}
        .issue-card:hover .issue-card-arrow span {{ transform: translate(2px, -2px); }}
        .empty-state {{ padding: 3rem; border: 1px solid var(--border); border-radius: 1.25rem; background: rgba(255,255,255,0.6); text-align: center; }}

        .site-footer {{ border-top: 1px solid #073D2D; background: var(--deep-forest); color: white; }}
        .footer-inner {{ min-height: 12rem; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 2rem; padding-block: 2.5rem; }}
        .footer-brand {{ display: inline-flex; align-items: center; gap: 0.85rem; }}
        .footer-brand svg {{ width: 3.5rem; height: 2.35rem; color: white; }}
        .footer-brand .brand-wordmark span {{ color: white; }}
        .footer-copy {{ margin: 1rem 0 0; color: rgba(255,255,255,0.62); font-size: 0.82rem; }}
        .footer-signature {{ margin: 0; color: white; font-family: var(--font-display); font-size: clamp(1.6rem, 3vw, 2.25rem); font-style: italic; font-weight: 600; text-align: right; }}
        .footer-link {{ display: inline-block; margin-top: 0.75rem; color: var(--builder-yellow); font-size: 0.75rem; font-weight: 700; text-decoration: none; }}

        @media (max-width: 900px) {{
            .hero {{ grid-template-columns: 1fr; min-height: 0; }}
            .hero-copy {{ max-width: 44rem; }}
            .latest-card {{ min-height: 27rem; }}
        }}
        @media (max-width: 640px) {{
            .shell {{ width: min(100% - 2rem, 80rem); }}
            .brand-wordmark {{ display: none; }}
            .studio-link {{ padding-inline: 0.8rem; font-size: 0.7rem; }}
            .hero {{ padding-block: 3.5rem 5rem; gap: 3.25rem; }}
            h1 span:last-child {{ font-size: clamp(3.25rem, 17vw, 5.1rem); white-space: normal; line-height: 0.88; }}
            .brand-stroke {{ width: 88%; }}
            .latest-card {{ min-height: 32rem; padding: 1.35rem; }}
            .latest-card-layout {{ grid-template-columns: 1fr; align-content: end; gap: 2rem; min-height: 25rem; padding-top: 2.5rem; }}
            .latest-date {{ width: 5.5rem; text-align: left; }}
            .latest-date strong {{ font-size: 5rem; }}
            .latest-copy h2 {{ font-size: 2.3rem; }}
            .archive-header {{ grid-template-columns: 1fr; gap: 1rem; margin-bottom: 3rem; }}
            .archive-grid {{ grid-template-columns: 1fr; }}
            .issue-card {{ min-height: 9.5rem; }}
            .footer-inner {{ grid-template-columns: 1fr; }}
            .footer-signature {{ text-align: left; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            html {{ scroll-behavior: auto; }}
            *, *::before, *::after {{ transition-duration: 0.001ms !important; animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; }}
        }}
        @media (forced-colors: active) {{
            .latest-card, .issue-card, .studio-link {{ border: 1px solid CanvasText; }}
        }}
    </style>
</head>
<body>
    <a class="skip-link" href="#archive">Skip to issue archive</a>
    <header class="site-header">
        <div class="shell site-header-inner">
            <a class="brand-lockup" href="https://wildernesstudio.com/" target="_blank" rel="noopener" aria-label="Visit Wilderness Studio">
                {MOUNTAIN_MARK}
                <span class="brand-wordmark"><span>Wilderness</span><span>Studio</span></span>
            </a>
            <a class="studio-link" href="https://wildernesstudio.com/" target="_blank" rel="noopener">Visit Studio <span aria-hidden="true">↗</span></a>
        </div>
    </header>

    <main>
        <section class="shell hero" aria-labelledby="page-title">
            <div class="hero-copy">
                <div class="product-label">A Wilderness Studio product</div>
                <h1 id="page-title"><span>HN</span><span>DAILY BRIEF</span></h1>
                <svg class="brand-stroke" viewBox="0 0 320 28" preserveAspectRatio="none" aria-hidden="true"><path d="M5 18 C74 5 148 24 226 12 C264 6 291 8 315 5"></path></svg>
                <p class="hero-description">Curated daily brief for AI-native builders. Relevant Hacker News signals, shaped into a clearer starting point for product, creative, and technical decisions.</p>
                <p class="hero-meta">{issue_count} editions · Updated daily</p>
                <div class="hero-tags" aria-label="Coverage areas"><span>AI signals</span><span>Developer tools</span><span>Product thinking</span></div>
            </div>
            {latest_html}
        </section>

        <section class="shell archive-section" id="archive" aria-labelledby="archive-title">
            <div class="archive-header">
                <div>
                    <p class="archive-eyebrow">Daily Issue Archive from wildernesstudio.com</p>
                    <h2 id="archive-title">Previous editions.</h2>
                </div>
                <div class="archive-count">{len(previous_issues)} previous issues</div>
            </div>
            {archive_html if archive_html else '<div class="empty-state">Previous issues will appear here.</div>'}
        </section>
    </main>

    <footer class="site-footer">
        <div class="shell footer-inner">
            <div>
                <div class="footer-brand">
                    {MOUNTAIN_MARK}
                    <span class="brand-wordmark"><span>Wilderness</span><span>Studio</span></span>
                </div>
                <p class="footer-copy">HN Daily Brief · A daily intelligence product for AI-native builders.</p>
            </div>
            <div>
                <p class="footer-signature">Experience leads. AI amplifies.</p>
                <a class="footer-link" href="https://wildernesstudio.com/" target="_blank" rel="noopener">wildernesstudio.com ↗</a>
            </div>
        </div>
    </footer>
</body>
</html>
'''

    html_template = "\n".join(line.rstrip() for line in html_template.splitlines()) + "\n"
    Path("index.html").write_text(html_template, encoding="utf-8")
    print(f"✅ Archive updated: index.html generated with {issue_count} issues.")


if __name__ == "__main__":
    updated_count = update_issue_pages()
    print(f"✅ Updated branding and navigation for {updated_count} issues.")
    generate_index()
