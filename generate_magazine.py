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
import time
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
# BILINGUAL TRANSLATION & LLM API (Google Gemini 1.5 Flash)
# ---------------------------------------------------------------------------

def call_gemini_llm(prompt, system_instruction=None, max_retries=3):
    """Call Google Gemini API natively using urllib with exponential backoff for Rate Limits."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("    [WARNING] GEMINI_API_KEY not found in environment. Translation will fail or be empty.")
        return ""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = { "contents": [{"parts": [{"text": prompt}]}] }
    
    if system_instruction:
        payload["systemInstruction"] = { "parts": [{"text": system_instruction}] }
        
    data = json.dumps(payload).encode('utf-8')
    
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                try:
                    text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
                    return text.strip()
                except (KeyError, IndexError):
                    return ""
        except Exception as e:
            is_rate_limit_or_server_error = isinstance(e, urllib.error.HTTPError) and e.code in [429, 404, 500, 502, 503, 504]
            wait_time = (attempt + 1) * 5 if is_rate_limit_or_server_error else 3
            
            if attempt < max_retries - 1:
                print(f"    [API ERROR] {e}. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"    [API FATAL] Failed after {max_retries} attempts: {e}")
                return ""
            
    return ""

def translate_text(text, target_lang='en'):
    """Translation disabled - English only version."""
    if not text or not text.strip():
        return ""
    return text  # Return original English, skip translation

def rewrite_title_llm(original_title, article_summary):
    """Rewrite Hacker News title into an essence-focused engaging title."""
    if not article_summary or len(article_summary) < 20:
        return original_title
    
    sys_prompt = "You are a senior editor for a tech magazine. You are given a raw Hacker News title and a summary of the article. Rewrite the title into a SINGLE clear, punchy, and highly informative headline that instantly tells the reader the essence of the news. Output ONLY the English title, without quotes."
    prompt = f"Original Title: {original_title}\n\nSummary: {article_summary}"
    res = call_gemini_llm(prompt, system_instruction=sys_prompt)
    # Remove quotes if LLM adds them
    if res:
        return res.strip('"').strip("'")
    return original_title

def generate_insight_llm(title, summary, score):
    """Generate a category label and a unique, content-aware deep insight in English only."""
    if not summary or len(summary) < 20:
        return ["💡 Worth Watching", "This story is trending among tech professionals today."]

    sys_prompt = "You are a senior tech editor. Based on the Hacker News title and summary, provide a category label (with an emoji) in English. Then, write a 2-3 sentence deep-dive analytical insight in ENGLISH. Format: [Category Label] | [Your English Insight here]"
    prompt = f"Title: {title}\nScore: {score}\nSummary: {summary}"
    res = call_gemini_llm(prompt, system_instruction=sys_prompt)
    if res:
        if "Your English Insight here" in res or "English Insight" in res and len(res) < 150:
            return ["💡 Worth Watching", "This story is trending among tech professionals today."]

        parts = [p.strip() for p in res.split("|")]
        if len(parts) >= 2:
            return [parts[0], parts[1]]
        elif len(parts) == 1:
            return [parts[0], "This story is trending among tech professionals today."]
    return ["💡 Worth Watching", "This story is trending among tech professionals today."]

def analyze_community_llm(title, comments_text):
    """Analyze community comments - English only."""
    if not comments_text or len(comments_text) < 20:
        return ["", ""]
    sys_prompt = "You are a tech community analyst. Read the following Hacker News comments. Write a 2-3 sentence analysis of the community's consensus in ENGLISH."
    prompt = f"Title: {title}\nComments:\n{comments_text}"
    res = call_gemini_llm(prompt, system_instruction=sys_prompt)
    if res:
        if "Your actual English analysis here" in res or "English Analysis" in res and len(res) < 100:
            return ["", ""]
        return [res.strip(), ""]
    return ["", ""]

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
            summary_en = f"[Source content could not be fetched]"
            print(f"    ⚠ Could not fetch content for: {story['title'][:50]}")

        # STEP 2: Fetch top community comments and analyze deeply
        top_comments = fetch_top_comments(story["id"], n=8)
        community_en = ""
        community_zh = ""
        raw_comments_text = ""
        if top_comments:
            raw_comments_text = "\n---\n".join([c[:300] for c in top_comments])
            comm_parts = analyze_community_llm(story["title"], raw_comments_text)
            community_en = comm_parts[0]
            community_zh = comm_parts[1] if len(comm_parts) > 1 else comm_parts[0]
            
        # STEP 2.5: Validation - If summary missing, use LLM to guess from comments
        if "[Source content could not be fetched]" in summary_en and raw_comments_text:
            sys_p = f"Based on the following community comments about a Hacker News post titled '{story['title']}', write a 2-sentence summary of what the article must be about. Do not mention 'the comments say', just summarize the inferred topic."
            guessed_summary = call_gemini_llm(raw_comments_text, system_instruction=sys_p)
            if guessed_summary and len(guessed_summary) > 20:
                summary_en = guessed_summary

        # STEP 3: Generate category and insight (Bilingual)
        insight_parts = generate_insight_llm(story["title"], summary_en, story["score"])
        cat_en = insight_parts[0] if insight_parts else ""
        insight_en = insight_parts[1] if len(insight_parts) > 1 else ""
        insight_zh = insight_parts[2] if len(insight_parts) > 2 else insight_en

        # STEP 4: Rewrite title - English only
        story["title_en"] = rewrite_title_llm(story["title"], summary_en)
        story["title_zh"] = story["title_en"]  # Same as English

        story["summary_en"] = summary_en
        story["summary_zh"] = summary_en  # Same as English

        story["insight_cat_en"] = cat_en
        story["insight_cat_zh"] = cat_en  # Same as English

        story["insight_en"] = insight_en
        story["insight_zh"] = insight_en  # Same as English

        story["community_en"] = community_en
        story["community_zh"] = community_en  # Same as English
        
        # Override original title for final HTML render
        story["title"] = story["title_en"]
        
        # Pace API requests to respect Rate Limits
        time.sleep(3)
        return story

    # Sequential enrichment to avoid rate limits and ensure quality (Single Worker)
    with ThreadPoolExecutor(max_workers=1) as executor:
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
    { "bg": "#FAF6F0", "accent": "#C84B31", "rule_color": "#D4C5B5", "numeral_color": "rgba(200,75,49,0.04)" },
    { "bg": "#F5F1EA", "accent": "#1B2A4A", "rule_color": "#C8BFB0", "numeral_color": "rgba(27,42,74,0.04)" },
    { "bg": "#FBF3F0", "accent": "#A63D40", "rule_color": "#D8C4BC", "numeral_color": "rgba(166,61,64,0.04)" },
    { "bg": "#F4F6F0", "accent": "#3D5A3E", "rule_color": "#C0CDBA", "numeral_color": "rgba(61,90,62,0.04)" },
    { "bg": "#F8F4EC", "accent": "#7A5C3D", "rule_color": "#D0C4B0", "numeral_color": "rgba(122,92,61,0.04)" },
    { "bg": "#F0F2F5", "accent": "#3A4A5C", "rule_color": "#BCC5CF", "numeral_color": "rgba(58,74,92,0.04)" },
    { "bg": "#F7F3EB", "accent": "#8B3A3A", "rule_color": "#D0C0A8", "numeral_color": "rgba(139,58,58,0.04)" },
    { "bg": "#F3F0F8", "accent": "#5A4A7A", "rule_color": "#C8BFD8", "numeral_color": "rgba(90,74,122,0.04)" },
    { "bg": "#F0F5F4", "accent": "#2A5A5A", "rule_color": "#B0C8C4", "numeral_color": "rgba(42,90,90,0.04)" },
    { "bg": "#EDEBE5", "accent": "#C84B31", "rule_color": "#C0BDB5", "numeral_color": "rgba(200,75,49,0.04)" },
]

def html_escape(text):
    # First decode any existing HTML entities to avoid double-encoding
    text = html_mod.unescape(str(text))
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def render_story_section(story, index, style):
    num = index + 1
    s = style

    # Text Setup
    title_en = html_escape(story["title"])
    sum_en = html_escape(story.get("summary_en", ""))
    insight_en = html_escape(story.get("insight_en", ""))
    cat_en = html_escape(story.get("insight_cat_en", ""))
    comm_en = html_escape(story.get("community_en", ""))

    # Flag
    flag_html = ""
    if story["flagged"]:
        flag_html = f'<div class="flag">⚡ Highly Relevant</div>'

    # Category Line
    section_header = f'<div class="story-category">{cat_en}</div>'

    # Headline
    headline = f'<h2 class="story-title"><a href="{story["url"]}" target="_blank" rel="noopener">{title_en}</a></h2>'

    # Summary Block
    summary_html = ""
    if sum_en:
        summary_html = f'<p class="story-summary">{sum_en}</p>'

    # Insight
    insight_html = ""
    if insight_en:
        insight_html = f'''
    <div class="story-insight">
        <div class="story-insight-label">Actionable Insight</div>
        <p class="story-insight-text">{insight_en}</p>
    </div>'''

    # Community Voice
    community_html = ""
    if comm_en:
        community_html = f'''
    <div class="story-community">
        <div class="story-community-label">Community Voice</div>
        <p class="story-community-text">{comm_en}</p>
    </div>'''

    # Meta
    meta_line = f'''
    <div class="story-meta">
        <span>{html_escape(story["domain"])}</span>
        <span>·</span>
        <span>{story["score"]} pts</span>
        <span>·</span>
        <span>{story["comments"]} comments</span>
        <span>·</span>
        <span>by {html_escape(story["by"])}</span>
    </div>'''

    # Links
    links_html = f'''
    <div class="story-links">
        <a href="{story['url']}" target="_blank" rel="noopener" class="story-link">Read Source →</a>
        <a href="{story['hn_url']}" target="_blank" rel="noopener" class="story-link">HN Discussion →</a>
    </div>'''

    numeral = f'<div class="story-num">{num}</div>'

    return f'''
    <section id="story-{num}" class="story" style="background:{s['bg']};">
        {numeral}
        <div class="story-content">
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
        flag_mark = ' ⚡' if story["flagged"] else ""
        toc_items += f'''
        <a href="#story-{i+1}" class="toc-item">
            <span class="toc-num">{i+1:02d}</span>
            <span class="toc-title">{html_escape(story["title"])}{flag_mark}</span>
            <span class="toc-score">{story["score"]} pts</span>
        </a>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Edition — {formatted_date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
        html {{ scroll-behavior: smooth; -webkit-font-smoothing: antialiased; }}
        body {{ font-family: 'Inter', sans-serif; background: #FAF6F0; color: #1A1A1A; line-height: 1.6; word-break: break-word; }}
        a {{ overflow-wrap: anywhere; }}
        a:hover {{ opacity: 0.7; }}

        /* Masthead */
        .masthead {{ min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 12vh 8vw; position: relative; }}
        .masthead::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: #C84B31; }}
        .masthead-label {{ font-size: 0.65rem; letter-spacing: 0.4em; text-transform: uppercase; color: #8C7A6B; font-weight: 500; margin-bottom: 40px; }}
        .masthead h1 {{ font-family: 'Instrument Serif', serif; font-size: clamp(4rem, 12vw, 9rem); font-weight: 400; line-height: 0.9; letter-spacing: -0.03em; color: #1A1A1A; margin-bottom: 24px; }}
        .masthead h1 em {{ font-style: italic; color: #C84B31; }}
        .masthead-date {{ font-family: 'Instrument Serif', serif; font-size: 1.2rem; font-style: italic; color: #8C7A6B; margin-bottom: 8px; }}
        .masthead-year {{ font-size: 0.75rem; letter-spacing: 0.2em; color: #B0A090; }}

        /* TOC */
        .toc {{ padding: 120px 8vw; max-width: 720px; margin: 0 auto; }}
        .toc-header {{ font-size: 0.6rem; letter-spacing: 0.3em; text-transform: uppercase; color: #8C7A6B; margin-bottom: 48px; }}
        .toc-header::after {{ content: ''; display: block; width: 30px; height: 2px; background: #C84B31; margin-top: 12px; }}
        .toc-item {{ display: flex; align-items: baseline; gap: 24px; padding: 16px 0; border-bottom: 1px solid rgba(0,0,0,0.05); text-decoration: none; color: inherit; transition: padding-left 0.2s; }}
        .toc-item:hover {{ padding-left: 12px; opacity: 0.7; }}
        .toc-num {{ font-family: 'Instrument Serif', serif; font-size: 0.85rem; color: rgba(0,0,0,0.2); min-width: 24px; }}
        .toc-title {{ font-family: 'Instrument Serif', serif; font-size: 1.3rem; font-weight: 400; flex-grow: 1; line-height: 1.3; }}
        .toc-score {{ font-size: 0.7rem; color: rgba(0,0,0,0.3); white-space: nowrap; }}

        /* Story Section */
        .story {{ min-height: 100vh; padding: 120px 8vw; display: flex; align-items: center; position: relative; }}
        .story-content {{ max-width: 760px; width: 100%; }}
        .story-category {{ font-size: 0.55rem; letter-spacing: 0.25em; text-transform: uppercase; color: #8C7A6B; margin-bottom: 32px; display: flex; align-items: center; gap: 16px; }}
        .story-category::after {{ content: ''; width: 32px; height: 1px; background: rgba(0,0,0,0.1); }}
        .story-title {{ font-family: 'Instrument Serif', serif; font-size: clamp(2.5rem, 5vw, 4rem); font-weight: 400; line-height: 1.1; letter-spacing: -0.02em; color: #1A1A1A; margin-bottom: 40px; }}
        .story-title a {{ color: inherit; text-decoration: none; }}
        .story-summary {{ font-family: 'Instrument Serif', serif; font-size: 1.15rem; line-height: 1.8; color: #3A3A3A; margin-bottom: 48px; max-width: 680px; }}
        .story-insight {{ padding: 28px 32px; border-left: 3px solid #C84B31; background: rgba(0,0,0,0.015); margin-bottom: 32px; }}
        .story-insight-label {{ font-size: 0.55rem; letter-spacing: 0.2em; text-transform: uppercase; color: #C84B31; font-weight: 600; margin-bottom: 12px; }}
        .story-insight-text {{ font-family: 'Instrument Serif', serif; font-size: 1.1rem; line-height: 1.7; color: #3A3A3A; font-style: italic; }}
        .story-community {{ padding: 24px 0; border-left: 2px solid #D4C5B5; padding-left: 24px; margin-bottom: 32px; }}
        .story-community-label {{ font-size: 0.55rem; letter-spacing: 0.2em; text-transform: uppercase; color: #8C7A6B; margin-bottom: 12px; }}
        .story-community-text {{ font-size: 0.9rem; line-height: 1.7; color: #6A6A6A; font-weight: 300; }}
        .story-meta {{ font-size: 0.7rem; color: #8C7A6B; letter-spacing: 0.05em; margin-bottom: 24px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
        .story-meta span:first-child {{ font-weight: 600; background: rgba(0,0,0,0.03); padding: 3px 8px; border-radius: 2px; }}
        .story-links {{ display: flex; gap: 32px; }}
        .story-link {{ font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: #C84B31; text-decoration: none; border-bottom: 1px solid #C84B31; padding-bottom: 2px; }}
        .story-num {{ position: absolute; top: 8%; right: 6vw; font-family: 'Instrument Serif', serif; font-size: clamp(10rem, 22vw, 20rem); font-weight: 400; color: rgba(200,75,49,0.04); line-height: 1; pointer-events: none; user-select: none; }}
        .flag {{ display: inline-flex; align-items: center; gap: 6px; background: #C84B31; color: #FAF6F0; padding: 4px 14px; border-radius: 2px; font-size: 0.6rem; font-weight: 600; letter-spacing: 0.12em; margin-bottom: 24px; }}

        /* Floating Action Bar */
        .action-bar {{ position: fixed; top: 20px; right: clamp(20px, 4vw, 40px); z-index: 9999; display: flex; gap: 12px; }}
        .action-btn {{ background: rgba(250,246,240,0.9); border: 1px solid rgba(0,0,0,0.08); padding: 8px 16px; border-radius: 30px; font-family: 'Inter', sans-serif; font-size: 0.75rem; font-weight: 600; cursor: pointer; backdrop-filter: blur(8px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); color: #1A1A1A; transition: all 0.2s; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }}
        .action-btn.primary {{ background: #1A1A1A; color: #FAF6F0; border: none; }}
        .action-btn:hover {{ opacity: 0.8; }}

        @media (max-width: 768px) {{
            .story {{ padding: 80px 24px; min-height: auto; }}
            .story-num {{ display: none; }}
            .toc {{ padding: 80px 24px; }}
            .toc-item {{ gap: 16px; }}
            .toc-title {{ font-size: 1.1rem; }}
            .masthead {{ padding: 12vh 24px; }}
        }}
    </style>
    </style>
</head>
<body>
    <!-- FLOATING ACTION BAR -->
    <div class="action-bar">
        <a href="#toc" class="action-btn" style="text-decoration:none;">🏠 目录</a>
        <button onclick="navigator.clipboard.writeText(window.location.href); alert('Link copied to clipboard!');" class="action-btn">🔗 Share</button>
        <a href="#" id="download-btn" class="action-btn primary" style="text-decoration:none;">⬇️ Download</a>
    </div>
    <script>
        // Set download link to the exact HTML file it's viewed from
        document.addEventListener('DOMContentLoaded', () => {{
            const btn = document.getElementById('download-btn');
            // If on the web, grab the last part of path, else fallback
            const filename = window.location.pathname.split('/').pop() || 'magazine.html';
            btn.href = window.location.href;
            btn.download = filename;
        }});
    </script>

    <!-- MASTHEAD -->
    <div class="masthead">
        <div class="masthead-label">A Curated Daily Digest</div>
        <h1>Morning<br><em>Edition</em></h1>
        <div class="masthead-date">{day_name}</div>
        <div class="masthead-year">{formatted_date}</div>
    </div>

    <!-- TABLE OF CONTENTS -->
    <div class="toc" id="toc">
        <div class="toc-header">In This Issue</div>
        <nav>{toc_items}</nav>
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
