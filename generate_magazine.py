#!/usr/bin/env python3
"""
Morning Edition — Daily HN Magazine Generator
New Yorker–inspired editorial design · Bilingual (EN/ZH) · Real content summaries
"""

import json
import os
import sys
import re
import html as html_mod
import datetime
import urllib.request
import urllib.parse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# BILINGUAL TRANSLATION API (Google Translate Free Endpoint)
# ---------------------------------------------------------------------------

def translate_text(text, target_lang='zh-CN'):
    """Translate text using the free Google Translate API without an API key."""
    if not text or not text.strip():
        return ""
    
    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=" + target_lang + "&dt=t&q=" + urllib.parse.quote(text)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # data[0] contains the translated segments
            translated = ''.join([part[0] for part in data[0] if part[0]])
            return translated
    except Exception as e:
        print(f"    Translation error for text portion: {e}")
        return ""

def translate_insight_category(category):
    """Pre-translated categories for consistency."""
    mapping = {
        "🔬 AI/ML Landscape": "🔬 AI/ML 发展图景",
        "🛠 Developer Tooling": "🛠 开发者工具",
        "🔒 Security & Privacy": "🔒 安全与隐私",
        "🎨 Creative Tools": "🎨 创意工具",
        "🔭 Science & Research": "🔭 科学与研究",
        "📊 Industry Signal": "📊 行业信号",
        "💡 Worth Watching": "💡 值得关注",
    }
    return mapping.get(category, category)

# ---------------------------------------------------------------------------
# HTML TEXT EXTRACTOR
# ---------------------------------------------------------------------------

class ArticleExtractor(HTMLParser):
    SKIP_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside',
                 'iframe', 'noscript', 'svg', 'form', 'button', 'input'}
    BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote',
                  'div', 'article', 'section', 'figcaption', 'td', 'th'}

    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._current = []
        self._skip_depth = 0
        self._in_block = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._flush()
            self._in_block = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._skip_depth == 0 and tag in self.BLOCK_TAGS:
            self._flush()
            self._in_block = False

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._current.append(text)

    def _flush(self):
        if self._current:
            text = ' '.join(self._current).strip()
            if len(text) > 40:
                self.paragraphs.append(text)
            self._current = []

    def get_text(self):
        self._flush()
        return self.paragraphs

def extract_article_text(html_content):
    extractor = ArticleExtractor()
    try:
        extractor.feed(html_content)
    except Exception:
        pass
    return extractor.get_text()

# Noise words to filter out from summaries
SUMMARY_NOISE = [
    'cookie', 'subscribe', 'sign up', 'newsletter', 'privacy policy',
    'terms of', 'accept all', 'we use cookies', 'manage preferences',
    'consent', 'gdpr', 'opt out', 'unsubscribe', 'advertisement',
    'sponsored', 'related articles', 'read more', 'share this',
    'follow us', 'join our', 'download the app',
]

def smart_summarize(paragraphs, max_sentences=6):
    if not paragraphs: return ""
    # Take more paragraphs for better coverage
    lead = paragraphs[:20]
    sentences = []
    for p in lead:
        p = html_mod.unescape(p)
        # Skip paragraphs that are mostly URLs or source links
        url_count = len(re.findall(r'https?://', p))
        word_count = len(p.split())
        if url_count > 0 and url_count / max(word_count, 1) > 0.2:
            continue
        for s in re.split(r'(?<=[.!?])\s+', p):
            s = s.strip()
            if len(s) > 30 and not any(noise in s.lower() for noise in SUMMARY_NOISE) \
               and not s.startswith('http') and not s.startswith('www.') \
               and not re.match(r'^\[?\d+\]', s):
                sentences.append(s)
    if not sentences: return ""
    return ' '.join(sentences[:max_sentences])

def fetch_hn_algolia_content(story_id):
    """Fetch story content from Hacker News Algolia API as fallback."""
    try:
        url = f"https://hn.algolia.com/api/v1/items/{story_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "MorningEdition/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Try story text first
            if data.get("text"):
                text = re.sub(r'<[^>]+>', ' ', data["text"])
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 40:
                    return text[:600]
            # Compile top comments as content summary
            children = data.get("children", [])
            top_texts = []
            for child in children[:5]:
                if child.get("text") and not child.get("deleted"):
                    ct = re.sub(r'<[^>]+>', ' ', child["text"])
                    ct = html_mod.unescape(ct)
                    ct = re.sub(r'\s+', ' ', ct).strip()
                    if len(ct) > 60:
                        top_texts.append(ct)
            if top_texts:
                # Use the longest substantive comment as a proxy for article content
                best = max(top_texts, key=len)
                return f"Community discussion highlights: {best[:500]}"
    except Exception as e:
        print(f"    Algolia fallback error: {e}")
    return ""

def generate_insight(title, tags, domain, score, summary_text):
    """Generate a category label and a unique, content-aware insight for each story."""
    title_lower = title.lower()
    summary_lower = summary_text.lower() if summary_text else ""
    combined = f"{title_lower} {summary_lower}"

    # --- Determine category with priority ordering (most specific first) ---
    category = ""
    if any(kw in combined for kw in ['privacy', 'security', 'encrypt', 'backdoor', 'vulnerability', 'hack', 'data collection', 'surveillance', 'tracking', 'breach']):
        category = "🔒 Security & Privacy"
    elif any(kw in combined for kw in ['physics', 'quantum', 'biology', 'space', 'research', 'science', 'neuroscience', 'astronomy', 'chemistry', 'genome', 'experiment']):
        category = "🔭 Science & Research"
    elif any(kw in combined for kw in ['design', 'creative', 'figma', 'blender', 'resolve', 'photo', 'art', 'illustration', 'typography', 'animation']):
        category = "🎨 Creative Tools"
    elif any(kw in combined for kw in ['llm', 'gpt', 'claude', 'copilot', 'machine learning', 'neural', 'transformer', 'diffusion', 'training', 'fine-tun', 'inference', 'token', 'benchmark']):
        category = "🔬 AI/ML Landscape"
    elif any(kw in combined for kw in ['dev tool', 'cli', 'ide', 'terminal', 'git', 'framework', 'sdk', 'compiler', 'debugger', 'linter', 'rust', 'python', 'typescript', 'database', 'sql', 'postgres', 'api']):
        category = "🛠 Developer Tooling"
    elif score > 500:
        category = "📊 Industry Signal"
    else:
        category = "💡 Worth Watching"

    # --- Generate content-aware insight text ---
    # Build insight based on what the story is actually about
    insight = _generate_contextual_insight(title_lower, summary_lower, domain, score, category)
    return [category, insight]

def _generate_contextual_insight(title, summary, domain, score, category):
    """Generate a varied, specific insight based on actual story content."""
    combined = f"{title} {summary}"
    
    # --- HIGH SPECIFICITY matches first (to avoid broad keyword collisions) ---
    
    # Acquisition / M&A / corporate deals
    if any(kw in combined for kw in ['acquir', 'acquisition', 'merger', 'buyout', 'purchase agreement']):
        return "Corporate acquisitions reshape ecosystem dynamics overnight. When major players consolidate, evaluate continuity risks for tools you depend on — pricing changes, API deprecation, and cultural shifts often follow within 6-12 months. Have contingency plans for critical dependencies."
    
    # CEO / leadership changes
    if any(kw in combined for kw in ['ceo', 'chairman', 'leadership', 'succession', 'executive', 'step down', 'retire']):
        return "Leadership transitions at major tech companies often signal strategic pivots. Watch for changes in product direction, R&D investment priorities, and partnership strategies in the coming quarters. These shifts can create both opportunities and risks for developers building on their platforms."
    
    # Pricing / subscription / plan changes  
    if any(kw in combined for kw in ['pricing', 'subscription', 'plan change', 'removed from', 'free tier', 'price increase', 'paywall', 'billing']):
        return "Pricing and access changes signal how companies view their product-market fit. When tools move behind paywalls or change tiers, evaluate whether the value proposition still holds for your use case. This is also a good moment to audit alternatives and ensure you're not locked into a single vendor."
    
    # Image generation / AI art
    if any(kw in combined for kw in ['image generat', 'text-to-image', 'dall-e', 'dalle', 'midjourney', 'stable diffusion', 'chatgpt image', 'ai art', 'image model']):
        return "AI image generation is rapidly becoming a standard capability across platforms. The competitive differentiation is shifting from raw quality to integration, speed, and style control. For product teams, the key question is whether to build on top of APIs or adopt integrated solutions that reduce workflow friction."
    
    # Video editing / creative production tools
    if any(kw in combined for kw in ['video edit', 'video studio', 'browser based editor', 'timeline', 'rendering', 'ffmpeg', 'creative tool']):
        return "Browser-based creative tools are closing the gap with desktop applications, driven by WebAssembly and GPU APIs. For teams producing content at scale, web-based tools offer collaboration advantages that native apps struggle to match. Evaluate whether the tradeoffs in raw performance are worth the gains in accessibility and workflow integration."
    
    # Python / scripting / APIs (BEFORE hardware — 'keyboard api' should match here)
    if any(kw in combined for kw in ['python', 'pip', 'pypi', 'api for', 'library for']):
        return "Developer-facing Python libraries and APIs that solve niche problems well tend to gain adoption faster than general-purpose alternatives. If this addresses a pain point in your workflow, the investment in learning a focused tool typically pays for itself within a few days of use."
    
    # Hardware / laptops / devices (removed 'keyboard' — too broad)
    if any(kw in combined for kw in ['laptop', 'hardware', 'framework laptop', 'thinkpad', 'macbook', 'chip', 'processor', 'soc', 'ram', 'ssd', 'display', 'repairabilit']):
        return "Hardware choices compound over years of daily use. When evaluating developer machines, prioritize repairability, upgrade paths, and ecosystem alignment over raw specs. A repairable laptop with good Linux support may deliver better long-term value than a sealed ultra-premium device."
    
    # Software engineering principles / wisdom / laws
    if any(kw in combined for kw in ['laws of', 'principles', 'engineering wisdom', 'best practice', 'philosophy of', 'lessons learned', 'software craft', 'engineering culture']):
        return "Timeless engineering principles endure precisely because they capture hard-won wisdom about complexity, communication, and trade-offs. Revisiting these fundamentals periodically helps recalibrate against the noise of trendy practices. The best engineers blend proven principles with contextual judgment."
    
    # Regulation / policy / EU (tightened: removed 'law' and 'battery' which are too broad)
    if any(kw in combined for kw in ['eu regulation', 'eu directive', 'eu mandate', 'legislation', 'compliance', 'right to repair', 'antitrust', 'gdpr', 'regulatory']):
        return "Regulatory changes create compliance obligations but also innovation opportunities. Companies that proactively adapt to new requirements — rather than treating them as burdens — often gain competitive advantages. Evaluate how this might affect your product roadmap and supply chain decisions."
    
    # OAuth / authentication / security breaches
    if any(kw in combined for kw in ['oauth', 'breach', 'attack', 'exploit', 'vulnerability', 'token', 'credential', 'phishing']):
        return "Authentication and authorization vulnerabilities remain one of the most exploited attack surfaces. Review your OAuth implementations, token scoping, and third-party integration permissions. A single misconfigured scope can cascade into a full platform compromise."
    
    # Open source projects / CLI tools / developer tools
    if any(kw in combined for kw in ['open source', 'open-source', 'oss', 'foss', 'self-host', 'self host']):
        return "The open-source ecosystem thrives on community trust and transparency. When evaluating OSS tools, look beyond stars and downloads — examine commit velocity, maintainer responsiveness, and license terms. A smaller but actively maintained project often outperforms popular but stagnating alternatives."
    
    # AI models / benchmarks / new releases
    if any(kw in combined for kw in ['model', 'benchmark', 'preview', 'smarter', 'state of the art', 'sota']):
        return "New model releases are accelerating — the gap between SOTA announcements is shrinking from months to weeks. Rather than chasing every new release, focus on which models best fit your specific use cases. Run your own evaluations on tasks that matter to your workflow before switching."
    
    # AI agents / tools / coding assistants
    if any(kw in combined for kw in ['agent', 'copilot', 'assistant', 'automat', 'workflow', 'pipeline', 'coding']):
        return "AI-augmented workflows are maturing from demos to production tools. The key differentiator is not raw capability but integration quality — how seamlessly a tool fits into existing processes. Prototype with a real task from your backlog before committing to adoption."
    
    # Data / privacy / corporate practices
    if any(kw in combined for kw in ['data collection', 'opt-out', 'consent', 'telemetry']):
        return "Default-on data collection is becoming a recurring pattern across SaaS platforms. Review your vendor agreements and admin settings proactively. Consider implementing a quarterly audit of third-party data sharing policies — the compliance landscape is shifting faster than most teams realize."
    
    # Security / vulnerabilities
    if any(kw in combined for kw in ['supply chain', 'backdoor', 'malware', 'ransomware']):
        return "Supply-chain and platform-level security risks require systemic responses, not just individual patches. Audit your dependency tree, enforce least-privilege access, and establish incident response playbooks before you need them. The cost of prevention is always lower than the cost of remediation."
    
    # Advertising / monetization
    if any(kw in combined for kw in ['ad placement', 'advertising', 'monetiz', 'ad revenue', 'sponsor']):
        return "The convergence of AI and advertising signals a fundamental shift in how digital products are monetized. As AI platforms introduce ad placements, evaluate the trade-offs between free AI tool access and the potential compromise of recommendation neutrality. Your prompt data may become the new cookie."
    
    # Fake / manipulation / trust
    if any(kw in combined for kw in ['fake', 'fraud', 'manipulation', 'authenticity', 'astroturf']):
        return "Trust metrics in open-source ecosystems are becoming unreliable as manipulation scales. Develop your own evaluation criteria beyond social proof — code quality, test coverage, documentation depth, and maintainer track record are harder to fake than stars and downloads."
    
    # Programming languages / systems / performance
    if any(kw in combined for kw in ['rust', 'zero-copy', 'memory', 'allocat', 'kernel', 'syscall', 'buffer', 'compiler']):
        return "Systems-level performance optimization remains a high-leverage skill. Understanding memory management patterns — even at a conceptual level — helps you make better architectural decisions. Consider whether these techniques apply to any performance-critical paths in your current projects."
    
    
    # Negotiation / fairness / game theory
    if any(kw in combined for kw in ['negotiat', 'fairness', 'bargain', 'mediator', 'game theory', 'nash', 'cooperat']):
        return "Applying formal models to subjective domains like negotiation is a promising frontier for AI applications. The challenge is capturing context that formal models miss — power dynamics, cultural norms, and emotional factors. Useful as a starting point, but human judgment remains essential."
    
    # Science / nature / historical data
    if any(kw in combined for kw in ['years old', 'historical', 'archive', 'heritage', 'preservation', 'blossom', 'nature']):
        return "Long-duration datasets are irreplaceable scientific assets. The challenge of knowledge transfer across generations mirrors what many organizations face with institutional knowledge. Consider how your team documents and preserves critical operational knowledge that exists only in people's heads."
    
    # Fallback based on engagement level
    if score > 500:
        return f"This story resonated strongly with the technical community ({score} points), suggesting it touches a widely-felt concern or marks a notable shift. High-engagement stories often precede broader industry changes — monitor downstream effects on tooling, policy, or market dynamics."
    elif score > 200:
        return f"With {score} points on HN, this signals growing interest in the space. While not yet mainstream, topics at this engagement level often represent emerging trends worth tracking. Set a reminder to revisit this topic in 3-6 months to see how it evolved."
    else:
        return "Emerging signals from niche communities often foreshadow broader shifts. Early awareness gives you the advantage of preparation time — even if this specific development doesn't pan out, the underlying trend it represents may be worth monitoring."

# ---------------------------------------------------------------------------
# FETCH
# ---------------------------------------------------------------------------

HN_API = "https://hacker-news.firebaseio.com/v0"

def fetch_json(url, retries=2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MorningEdition/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries: return None

# Multiple user-agent strings for better fetch success
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

def fetch_html(url, timeout=12):
    """Fetch HTML with multiple user-agent fallbacks for better success rate."""
    for ua in _USER_AGENTS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "identity",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get('Content-Type', '')
                if 'text/html' not in content_type and 'text/plain' not in content_type:
                    return None
                raw = resp.read(800_000)  # Read more content
                try:
                    return raw.decode('utf-8')
                except UnicodeDecodeError:
                    return raw.decode('latin-1', errors='replace')
        except Exception:
            continue
    return None

def fetch_top_comments(story_id, n=3):
    story = fetch_json(f"{HN_API}/item/{story_id}.json")
    if not story or not story.get("kids"): return []
    comments = []
    for kid_id in story["kids"][:n * 2]:
        item = fetch_json(f"{HN_API}/item/{kid_id}.json")
        if item and item.get("text") and not item.get("deleted") and not item.get("dead"):
            text = re.sub(r'<[^>]+>', ' ', item["text"])
            text = html_mod.unescape(text)  # Decode HTML entities like &#x2F; &gt; &quot;
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 50: comments.append(text)
            if len(comments) >= n: break
    return comments

def fetch_top_stories(n=60):
    ids = fetch_json(f"{HN_API}/topstories.json")
    if not ids: sys.exit(1)
    return ids[:n]

def fetch_story(story_id):
    data = fetch_json(f"{HN_API}/item/{story_id}.json")
    if data and data.get("type") == "story" and data.get("title"): return data
    return None

def fetch_all_stories(story_ids):
    stories = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(fetch_story, sid): sid for sid in story_ids}
        for future in as_completed(futures):
            res = future.result()
            if res: stories.append(res)
    return stories

def extract_domain(url):
    if not url: return "news.ycombinator.com"
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain[4:] if domain.startswith("www.") else domain
    except Exception: return "unknown"

def score_story(story, config):
    taste = config.get("taste", {})
    boost_kw = taste.get("boost_keywords", [])
    skip_kw = taste.get("skip_keywords", [])
    flag_kw = taste.get("flag_for_me_keywords", [])

    title = story.get("title", "").lower()
    url = story.get("url", "").lower()
    domain = extract_domain(story.get("url", ""))
    searchable = f"{title} {url} {domain}"

    for kw in skip_kw:
        if kw.lower() in searchable: return (-100, False, ["skip"])

    taste_score = sum(3 for kw in boost_kw if kw.lower() in searchable)
    tags = [kw for kw in boost_kw if kw.lower() in searchable]
    
    flagged = any(kw.lower() in searchable for kw in flag_kw)
    if flagged: tags.extend([f"⚡{kw}" for kw in flag_kw if kw.lower() in searchable])

    hn_score = story.get("score", 0)
    combined = (taste_score * 100) + hn_score
    return (combined, flagged, list(set(tags))[:4])

def curate_stories(stories, config, n=10):
    scored = []
    for s in stories:
        combined, flagged, tags = score_story(s, config)
        if combined < 0: continue
        scored.append({
            "id": s.get("id"),
            "title": s.get("title", "Untitled"),
            "url": s.get("url", f"https://news.ycombinator.com/item?id={s['id']}"),
            "hn_url": f"https://news.ycombinator.com/item?id={s['id']}",
            "score": s.get("score", 0), "comments": s.get("descendants", 0),
            "by": s.get("by", "anonymous"), "domain": extract_domain(s.get("url", "")),
            "flagged": flagged, "tags": tags, "time": s.get("time", 0), "combined_score": combined,
        })
    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    return scored[:n]

def enrich_stories(curated):
    print("   Fetching content and translating (this may take a moment)...")

    def enrich_one(story):
        # STEP 1: Try to get article content from multiple sources
        summary_en = ""
        
        # For Show HN posts, try HN post body text first (most reliable)
        if story["title"].lower().startswith("show hn") or story["domain"] == "news.ycombinator.com":
            item = fetch_json(f"{HN_API}/item/{story['id']}.json")
            if item and item.get("text"):
                text = re.sub(r'<[^>]+>', ' ', item["text"])
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Exclude if it's just a bunch of URLs
                url_count = len(re.findall(r'https?://', text))
                word_count = max(len(text.split()), 1)
                
                if len(text) > 40 and (url_count / word_count) < 0.2:
                    summary_en = text[:600]
        
        # Try fetching the actual article HTML
        if not summary_en:
            html_content = fetch_html(story["url"])
            if html_content:
                paragraphs = extract_article_text(html_content)
                summary_en = smart_summarize(paragraphs, max_sentences=5)
        
        # Fallback: Try HN post body for non-Show-HN posts too
        if not summary_en:
            item = fetch_json(f"{HN_API}/item/{story['id']}.json")
            if item and item.get("text"):
                text = re.sub(r'<[^>]+>', ' ', item["text"])
                text = html_mod.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()
                
                url_count = len(re.findall(r'https?://', text))
                word_count = max(len(text.split()), 1)
                
                if len(text) > 40 and (url_count / word_count) < 0.2:
                    summary_en = text[:600]
        
        # Fallback: Try Algolia API for richer content
        if not summary_en:
            summary_en = fetch_hn_algolia_content(story["id"])
        
        # Final fallback: construct a minimal but honest summary from title context
        if not summary_en:
            summary_en = f"This story about \"{story['title']}\" from {story['domain']} generated significant discussion with {story['score']} points and {story.get('comments', 0)} comments on Hacker News. [Source content could not be fetched — visit the link below for full details.]"
            print(f"    ⚠ Could not fetch content for: {story['title'][:50]}")

        # STEP 2: Fetch top community comments
        top_comments = fetch_top_comments(story["id"], n=3)
        community_en = ""
        if top_comments:
            # Pick the most substantive comment (not just longest)
            scored_comments = []
            for c in top_comments:
                # Penalize comments that are just quoting the article
                quote_ratio = c.count('>') / max(len(c.split()), 1)
                substance = len(c) * (1 - min(quote_ratio, 0.5))
                scored_comments.append((substance, c))
            scored_comments.sort(key=lambda x: x[0], reverse=True)
            best = scored_comments[0][1]
            community_en = best[:350] + "..." if len(best) > 350 else best

        # STEP 3: Generate category and insight (now content-aware)
        insight_parts = generate_insight(story["title"], story["tags"], story["domain"], story["score"], summary_en)
        cat_en = insight_parts[0] if insight_parts else ""
        insight_en = insight_parts[1] if len(insight_parts) > 1 else ""

        # STEP 4: Translate all text
        story["title_zh"] = translate_text(story["title"])
        story["summary_en"] = summary_en
        story["summary_zh"] = translate_text(summary_en)
        
        story["insight_cat_en"] = cat_en
        story["insight_cat_zh"] = translate_insight_category(cat_en)
        
        story["insight_en"] = insight_en
        story["insight_zh"] = translate_text(insight_en)
        
        story["community_en"] = community_en
        story["community_zh"] = translate_text(community_en)
        
        return story

    # Sequential enrichment to avoid rate limits and ensure quality
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(enrich_one, s): i for i, s in enumerate(curated)}
        results = [None] * len(curated)
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            has_content = "[Source content could not be fetched" not in results[idx].get("summary_en", "")
            status = "✓" if has_content else "⚠"
            print(f"   {status} [{idx+1:2d}/10] {results[idx]['title'][:50]} | 翻译完成")

    return results

# ---------------------------------------------------------------------------
# RENDER — BILINGUAL EDITORIAL DESIGN
# ---------------------------------------------------------------------------

PAGE_STYLES = [
    { "bg": "#FAF6F0", "border_accent": "#C84B31", "heading_color": "#1A1A1A", "text_color": "#2D2D2D", "meta_color": "#8C7A6B", "accent": "#C84B31", "label_bg": "#C84B31", "label_color": "#FAF6F0", "rule_color": "#D4C5B5", "numeral_color": "rgba(200,75,49,0.06)", "layout": "hero" },
    { "bg": "#F5F1EA", "border_accent": "#1B2A4A", "heading_color": "#1B2A4A", "text_color": "#3A3A3A", "meta_color": "#7A8BA0", "accent": "#1B2A4A", "label_bg": "#1B2A4A", "label_color": "#F5F1EA", "rule_color": "#C8BFB0", "numeral_color": "rgba(27,42,74,0.05)", "layout": "standard" },
    { "bg": "#FBF3F0", "border_accent": "#A63D40", "heading_color": "#2A1A16", "text_color": "#3D2D28", "meta_color": "#A08070", "accent": "#A63D40", "label_bg": "#A63D40", "label_color": "#FBF3F0", "rule_color": "#D8C4BC", "numeral_color": "rgba(166,61,64,0.05)", "layout": "pull-quote" },
    { "bg": "#F4F6F0", "border_accent": "#3D5A3E", "heading_color": "#1A2E1A", "text_color": "#2D3D2D", "meta_color": "#6B8A6B", "accent": "#3D5A3E", "label_bg": "#3D5A3E", "label_color": "#F4F6F0", "rule_color": "#C0CDBA", "numeral_color": "rgba(61,90,62,0.05)", "layout": "two-column" },
    { "bg": "#F8F4EC", "border_accent": "#7A5C3D", "heading_color": "#2A2015", "text_color": "#3A3025", "meta_color": "#9A8A70", "accent": "#7A5C3D", "label_bg": "#7A5C3D", "label_color": "#F8F4EC", "rule_color": "#D0C4B0", "numeral_color": "rgba(122,92,61,0.05)", "layout": "drop-cap" },
    { "bg": "#F0F2F5", "border_accent": "#3A4A5C", "heading_color": "#1A2A3A", "text_color": "#2D3D4D", "meta_color": "#7A8A9A", "accent": "#3A4A5C", "label_bg": "#3A4A5C", "label_color": "#F0F2F5", "rule_color": "#BCC5CF", "numeral_color": "rgba(58,74,92,0.05)", "layout": "stat-callout" },
    { "bg": "#F7F3EB", "border_accent": "#8B3A3A", "heading_color": "#1A1A1A", "text_color": "#333333", "meta_color": "#9A8575", "accent": "#8B3A3A", "label_bg": "#8B3A3A", "label_color": "#F7F3EB", "rule_color": "#D0C0A8", "numeral_color": "rgba(139,58,58,0.05)", "layout": "aside-quote" },
    { "bg": "#F3F0F8", "border_accent": "#5A4A7A", "heading_color": "#2A1A3A", "text_color": "#3A2D4A", "meta_color": "#8A7AA0", "accent": "#5A4A7A", "label_bg": "#5A4A7A", "label_color": "#F3F0F8", "rule_color": "#C8BFD8", "numeral_color": "rgba(90,74,122,0.05)", "layout": "standard" },
    { "bg": "#F0F5F4", "border_accent": "#2A5A5A", "heading_color": "#1A2E2E", "text_color": "#2D3E3E", "meta_color": "#6A9090", "accent": "#2A5A5A", "label_bg": "#2A5A5A", "label_color": "#F0F5F4", "rule_color": "#B0C8C4", "numeral_color": "rgba(42,90,90,0.05)", "layout": "pull-quote" },
    { "bg": "#EDEBE5", "border_accent": "#2A2A2A", "heading_color": "#1A1A1A", "text_color": "#2D2D2D", "meta_color": "#7A7A70", "accent": "#2A2A2A", "label_bg": "#C84B31", "label_color": "#EDEBE5", "rule_color": "#C0BDB5", "numeral_color": "rgba(42,42,42,0.06)", "layout": "closer" },
]

def html_escape(text):
    # First decode any existing HTML entities to avoid double-encoding
    text = html_mod.unescape(str(text))
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def render_story_section(story, index, style):
    num = index + 1
    s = style
    layout = s["layout"]
    
    # Text Setup
    title_en = html_escape(story["title"])
    title_zh = html_escape(story.get("title_zh", ""))
    
    sum_en = html_escape(story.get("summary_en", ""))
    sum_zh = html_escape(story.get("summary_zh", ""))
    
    insight_en = html_escape(story.get("insight_en", ""))
    insight_zh = html_escape(story.get("insight_zh", ""))
    
    cat_en = html_escape(story.get("insight_cat_en", ""))
    cat_zh = html_escape(story.get("insight_cat_zh", ""))
    
    comm_en = html_escape(story.get("community_en", ""))
    comm_zh = html_escape(story.get("community_zh", ""))

    # Flag
    flag_html = ""
    if story["flagged"]:
        flag_html = f'''
        <div style="display:inline-flex;align-items:center;gap:6px;background:{s['label_bg']};color:{s['label_color']};
            padding:4px 14px;border-radius:2px;font-family:'Inter',sans-serif;font-size:0.7rem;
            font-weight:700;letter-spacing:0.12em;margin-bottom:24px;">
            ⚡ HIGHLY RELEVANT TO YOU / 高度相关
        </div>'''

    # Category Line
    section_header = f'''
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:32px;">
        <span style="font-family:'Fraunces',serif;font-size:0.85rem;font-weight:400;color:{s['meta_color']};letter-spacing:0.05em;">{num:02d}</span>
        <span style="width:40px;height:1px;background:{s['rule_color']};"></span>
        <span style="font-family:'Inter',sans-serif;font-size:0.65rem;font-weight:600;color:{s['meta_color']};letter-spacing:0.18em;text-transform:uppercase;">
            {cat_en} &nbsp;|&nbsp; {cat_zh}
        </span>
    </div>'''

    # Bilingual Headline
    headline = f'''<div style="margin:0 0 32px 0;max-width:760px;">
        <h2 style="font-family:'Fraunces',serif;font-size:clamp(1.7rem,3vw,2.5rem);font-weight:800;line-height:1.15;letter-spacing:-0.02em;color:{s['heading_color']};margin:0 0 12px 0;">
            <a href="{story['url']}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;transition:opacity 0.2s;">{title_en}</a>
        </h2>
        <h3 style="font-family:'Noto Serif SC',serif;font-size:clamp(1.3rem,2.2vw,1.8rem);font-weight:600;line-height:1.4;color:{s['meta_color']};margin:0;">
            {title_zh}
        </h3>
    </div>'''

    # Bilingual Summary Block
    summary_html = ""
    if sum_en:
        summary_html = f'''
        <div class="bilingual-block" style="margin-bottom:24px;max-width:680px;">
            <p style="font-family:'Fraunces',serif;font-size:clamp(1rem,1.3vw,1.15rem);line-height:1.75;color:{s['text_color']};margin:0 0 12px 0;">{sum_en}</p>
            <p style="font-family:'Noto Serif SC',serif;font-size:1rem;line-height:1.8;color:{s['meta_color']};margin:0;">{sum_zh}</p>
        </div>'''

    # Bilingual Actionable Insight
    insight_html = ""
    if insight_en:
        insight_html = f'''
    <div style="margin-top:32px;padding:24px 28px;border-left:3px solid {s['accent']};background:rgba(0,0,0,0.02);border-radius:0 4px 4px 0;">
        <div style="font-family:'Inter',sans-serif;font-size:0.65rem;font-weight:700;color:{s['accent']};letter-spacing:0.15em;text-transform:uppercase;margin-bottom:12px;">
            Actionable Insight / 洞察与行动
        </div>
        <div class="bilingual-block">
            <p style="font-family:'Fraunces',serif;font-size:1rem;line-height:1.7;color:{s['text_color']};font-style:italic;margin:0 0 12px 0;">{insight_en}</p>
            <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.9rem;line-height:1.7;color:{s['meta_color']};margin:0;">{insight_zh}</p>
        </div>
    </div>'''

    # Bilingual Community Voice
    community_html = ""
    if comm_en:
        community_html = f'''
    <div style="margin-top:28px;padding-left:24px;border-left:2px solid {s['rule_color']};">
        <div style="font-family:'Inter',sans-serif;font-size:0.6rem;font-weight:600;color:{s['meta_color']};letter-spacing:0.15em;text-transform:uppercase;margin-bottom:12px;">
            Community Voice / 社区声音
        </div>
        <div class="bilingual-block">
            <p style="font-family:'Inter',sans-serif;font-size:0.9rem;line-height:1.6;color:{s['meta_color']};margin:0 0 8px 0;font-style:italic;">"{comm_en}"</p>
            <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.85rem;line-height:1.6;color:{s['meta_color']};opacity:0.8;margin:0;">"{comm_zh}"</p>
        </div>
    </div>'''

    # Meta
    meta_line = f'''
    <div style="font-family:'Inter',sans-serif;font-size:0.75rem;color:{s['meta_color']};letter-spacing:0.06em;margin-top:28px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <span style="font-weight:600;background:rgba(0,0,0,0.05);padding:3px 8px;border-radius:2px;">{html_escape(story["domain"])}</span>
        <span style="opacity:0.5;">·</span>
        <span>{story["score"]} pts</span>
        <span style="opacity:0.5;">·</span>
        <span>{story["comments"]} cmts</span>
        <span style="opacity:0.5;">·</span>
        <span>by {html_escape(story["by"])}</span>
    </div>'''

    # Links
    links_html = f'''
    <div style="display:flex;gap:24px;margin-top:24px;flex-wrap:wrap;">
        <a href="{story['url']}" target="_blank" rel="noopener" style="font-family:'Inter',sans-serif;font-size:0.75rem;font-weight:600;color:{s['accent']};text-decoration:none;letter-spacing:0.06em;text-transform:uppercase;border-bottom:1.5px solid {s['accent']};padding-bottom:2px;transition:opacity 0.2s;">
            Read Source / 阅读原稿 →
        </a>
        <a href="{story['hn_url']}" target="_blank" rel="noopener" style="font-family:'Inter',sans-serif;font-size:0.75rem;font-weight:600;color:{s['meta_color']};text-decoration:none;letter-spacing:0.06em;text-transform:uppercase;border-bottom:1px solid {s['rule_color']};padding-bottom:2px;transition:opacity 0.2s;">
            HN Discussion / 参与讨论 →
        </a>
    </div>'''

    numeral = f'''<div style="position:absolute;top:-4vw;right:4vw;font-family:'Fraunces',serif;font-size:clamp(8rem,18vw,16rem);font-weight:900;color:{s['numeral_color']};line-height:1;pointer-events:none;user-select:none;" aria-hidden="true">{num}</div>'''

    # Simplified Layouts since bilingual text takes more height:
    # Most will route through standard two-column concept or stacked.
    
    if layout == "two-column" or layout == "aside-quote":
        return f'''
    <section id="story-{num}" style="background:{s['bg']};min-height:100vh;padding:clamp(60px,10vh,100px) clamp(32px,8vw,100px);position:relative;overflow:hidden;display:flex;align-items:center;">
        {numeral}
        <div style="position:relative;z-index:2;width:100%;max-width:1100px;margin:0 auto;">
            {section_header}
            {flag_html}
            {headline}
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:clamp(32px,4vw,60px);margin-top:24px;" class="two-col-grid">
                <div>
                    {summary_html}
                    {meta_line}
                    {links_html}
                </div>
                <div>
                    {insight_html}
                    {community_html}
                </div>
            </div>
        </div>
    </section>'''

    return f'''
    <section id="story-{num}" style="background:{s['bg']};min-height:100vh;padding:clamp(60px,10vh,100px) clamp(32px,8vw,100px);position:relative;overflow:hidden;display:flex;align-items:center;">
        {numeral}
        <div style="position:relative;z-index:2;width:100%;max-width:860px;margin:0 auto;">
            {section_header}
            {flag_html}
            {headline}
            {summary_html}
            {insight_html}
            {community_html}
            {meta_line}
            {links_html}
        </div>
    </section>'''

def render_magazine(stories, date_str):
    sections = [render_story_section(story, i, PAGE_STYLES[i % len(PAGE_STYLES)]) for i, story in enumerate(stories)]
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = dt.strftime("%B %d, %Y")
        day_name = dt.strftime("%A")
    except:
        formatted_date = date_str; day_name = ""

    toc_items = ""
    for i, story in enumerate(stories):
        flag_mark = ' <span style="color:#C84B31;">⚡</span>' if story["flagged"] else ""
        toc_items += f'''
        <a href="#story-{i+1}" style="display:flex;align-items:baseline;gap:20px;text-decoration:none;padding:12px 0;border-bottom:1px solid rgba(0,0,0,0.05);transition:padding-left 0.2s;" onmouseover="this.style.paddingLeft='12px'" onmouseout="this.style.paddingLeft='0'">
            <span style="font-family:'Fraunces',serif;font-size:0.9rem;color:rgba(0,0,0,0.25);font-weight:600;min-width:24px;">{i+1:02d}</span>
            <div style="flex-grow:1;margin-right:20px;">
                <div style="font-family:'Fraunces',serif;font-size:clamp(1rem,1.2vw,1.15rem);color:#1A1A1A;font-weight:600;line-height:1.3;margin-bottom:4px;">{html_escape(story["title"])}{flag_mark}</div>
                <div style="font-family:'Noto Serif SC',serif;font-size:clamp(0.85rem,1vw,0.95rem);color:#8C7A6B;line-height:1.4;">{html_escape(story.get("title_zh",""))}</div>
            </div>
            <span style="font-family:'Inter',sans-serif;font-size:0.75rem;color:rgba(0,0,0,0.3);white-space:nowrap;">{story["score"]} pts</span>
        </a>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Edition — {formatted_date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,400..900;1,400..900&family=Inter:wght@400;600;700&family=Noto+Serif+SC:wght@400;600&family=Noto+Sans+SC:wght@400;500&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
        html {{ scroll-snap-type: y mandatory; scroll-behavior: smooth; -webkit-font-smoothing: antialiased; }}
        body {{ font-family: 'Inter', sans-serif; overflow-x: hidden; background: #FAF6F0; }}
        section {{ scroll-snap-align: start; scroll-snap-stop: always; }}
        a:hover {{ opacity: 0.8; }}
        .masthead {{ scroll-snap-align: start; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 8vh 6vw; position: relative; }}
        .masthead::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: #C84B31; }}
        .toc {{ scroll-snap-align: start; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: clamp(60px,10vh,100px) clamp(32px,12vw,200px); }}
        .nav-dots {{ position: fixed; right: clamp(12px,2vw,24px); top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 10px; z-index: 1000; }}
        .colophon {{ background: #EDEBE5; padding: 6vh 8vw; text-align: center; scroll-snap-align: end; }}
        @media (max-width: 768px) {{
            .nav-dots {{ display: none; }}
            section, .toc {{ padding: 48px 24px !important; }}
            .two-col-grid {{ grid-template-columns: 1fr !important; gap: 32px !important; }}
        }}
    </style>
</head>
<body>
    <!-- FLOATING ACTION BAR -->
    <div style="position: fixed; top: 20px; right: clamp(20px, 4vw, 40px); z-index: 9999; display: flex; gap: 12px;">
        <button onclick="navigator.clipboard.writeText(window.location.href); alert('Link copied to clipboard!');" style="background: rgba(250,246,240,0.9); border: 1px solid rgba(0,0,0,0.08); padding: 8px 16px; border-radius: 30px; font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; cursor: pointer; backdrop-filter: blur(8px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); color: #1A1A1A; transition: all 0.2s;" onmouseover="this.style.transform='translateY(-2px)';" onmouseout="this.style.transform='translateY(0)';">🔗 Share</button>
        <a href="#" id="download-btn" style="text-decoration: none; background: #1A1A1A; color: #FAF6F0; border: none; padding: 8px 16px; border-radius: 30px; font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.15); transition: all 0.2s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 16px rgba(0,0,0,0.2)';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)';">⬇️ Download</a>
    </div>
    <script>
        // Set download link to the exact HTML file it's viewed from
        document.addEventListener('DOMContentLoaded', () => {
            const btn = document.getElementById('download-btn');
            // If on the web, grab the last part of path, else fallback
            const filename = window.location.pathname.split('/').pop() || 'magazine.html';
            btn.href = window.location.href;
            btn.download = filename;
        });
    </script>

    <!-- MASTHEAD -->
    <div class="masthead">
        <div style="margin-bottom:40px;">
            <div style="width:60px;height:1px;background:#C84B31;margin:0 auto 20px;"></div>
            <span style="font-family:'Inter',sans-serif;font-size:0.65rem;font-weight:600;letter-spacing:0.3em;text-transform:uppercase;color:#8C7A6B;">
                A Curated Daily Digest · 中英双语晨报
            </span>
        </div>
        <h1 style="font-family:'Fraunces',serif;font-size:clamp(3.5rem,10vw,8rem);font-weight:900;color:#1A1A1A;line-height:0.95;letter-spacing:-0.03em;margin-bottom:16px;">
            Morning<br><em style="font-style:italic;font-weight:400;color:#C84B31;">Edition</em>
        </h1>
        <div style="width:40px;height:1px;background:#D4C5B5;margin:24px auto;"></div>
        <div style="font-family:'Fraunces',serif;font-size:clamp(1rem,1.8vw,1.3rem);color:#8C7A6B;font-weight:400;font-style:italic;">{day_name}</div>
        <div style="font-family:'Inter',sans-serif;font-size:clamp(0.8rem,1.2vw,0.95rem);color:#B0A090;font-weight:400;letter-spacing:0.1em;margin-top:6px;">{formatted_date}</div>
    </div>

    <!-- TABLE OF CONTENTS -->
    <div class="toc">
        <div style="max-width:700px;margin:0 auto;width:100%;">
            <div style="margin-bottom:40px;">
                <span style="font-family:'Inter',sans-serif;font-size:0.65rem;font-weight:600;letter-spacing:0.25em;text-transform:uppercase;color:#8C7A6B;">
                    In This Issue / 本期提要
                </span>
                <div style="width:30px;height:2px;background:#C84B31;margin-top:12px;"></div>
            </div>
            <nav>{toc_items}</nav>
        </div>
    </div>

    <!-- STORIES -->
    {"".join(sections)}

    <!-- COLOPHON -->
    <footer class="colophon">
        <div style="width:30px;height:1px;background:#C84B31;margin:0 auto 20px;"></div>
        <div style="font-family:'Fraunces',serif;font-size:1.2rem;color:#1A1A1A;font-style:italic;margin-bottom:8px;">Morning Edition</div>
        <div style="font-family:'Inter',sans-serif;font-size:0.7rem;color:#8C7A6B;letter-spacing:0.08em;">Curated from Hacker News · {formatted_date}</div>
        <div style="font-family:'Noto Sans SC',sans-serif;font-size:0.65rem;color:#B0A090;margin-top:8px;letter-spacing:0.05em;">双语精排版 · 为技术人定制的每日视角</div>
    </footer>
</body>
</html>'''

def main():
    print("=" * 60)
    print("  ☕  MORNING EDITION  —  Bilingual Editorial Design")
    print("=" * 60)
    config = load_config()
    today = datetime.date.today().strftime("%Y-%m-%d")
    output_dir = os.path.join(SCRIPT_DIR, config.get("output_dir", "magazines"))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{today}.html")

    print(f"\n📡 Fetching stories...")
    story_ids = fetch_top_stories(60)
    stories = fetch_all_stories(story_ids)

    print(f"\n🎯 Curating to taste...")
    curated = curate_stories(stories, config, 10)

    # Fill
    if len(curated) < 10:
        existing = {s["title"] for s in curated}
        for s in sorted(stories, key=lambda x: x.get("score", 0), reverse=True):
            if len(curated) >= 10: break
            if s.get("title") not in existing:
                curated.append({"id": s.get("id"), "title": s.get("title", "Untitled"), "url": s.get("url", f"https://news.ycombinator.com/item?id={s['id']}"), "hn_url": f"https://news.ycombinator.com/item?id={s['id']}", "score": s.get("score", 0), "comments": s.get("descendants", 0), "by": s.get("by", "anonymous"), "domain": extract_domain(s.get("url", "")), "flagged": False, "tags": [], "time": s.get("time", 0), "combined_score": s.get("score", 0)})
                existing.add(s.get("title"))

    print(f"\n📖 Enriching & Translating... (Using Google Translate)")
    curated = enrich_stories(curated)

    print(f"\n🎨 Rendering bilingual magazine...")
    html = render_magazine(curated, today)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✅ Saved to {output_path}")
    print(f"\n{'=' * 60}\n  ✅ Done! Restart the file to view.\n{'=' * 60}")

if __name__ == "__main__":
    main()
