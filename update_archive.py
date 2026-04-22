import os
import glob
from datetime import datetime

def generate_index():
    magazines_dir = "magazines"
    if not os.path.exists(magazines_dir):
        print(f"Directory {magazines_dir} does not exist.")
        return

    # Find all html files
    html_files = glob.glob(os.path.join(magazines_dir, "*.html"))
    
    # Sort files by date descending (assuming filename is YYYY-MM-DD.html)
    html_files.sort(reverse=True)

    items_html = ""
    for path in html_files:
        filename = os.path.basename(path)
        date_str = filename.replace(".html", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            display_date = dt.strftime("%B %d, %Y")
        except:
            display_date = date_str

        items_html += f'''
        <a href="magazines/{filename}" class="issue-card">
            <div class="issue-date">{display_date}</div>
            <div class="issue-title">Morning Edition - {date_str}</div>
            <div class="issue-arrow">→</div>
        </a>
        '''

    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Edition Archive</title>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,400..900;1,400..900&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: #FAF6F0; color: #1A1A1A; line-height: 1.6; padding: 40px 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        header {{ text-align: center; margin-bottom: 60px; }}
        h1 {{ font-family: 'Fraunces', serif; font-size: clamp(2.5rem, 6vw, 4rem); font-weight: 900; color: #1A1A1A; margin-bottom: 12px; letter-spacing: -0.02em; }}
        .subtitle {{ font-size: 0.9rem; color: #8C7A6B; text-transform: uppercase; letter-spacing: 0.15em; font-weight: 600; }}
        .rule {{ width: 60px; height: 2px; background: #C84B31; margin: 24px auto; }}
        
        .archive-grid {{ display: flex; flex-direction: column; gap: 16px; }}
        .issue-card {{ 
            display: flex; align-items: center; justify-content: space-between; 
            background: #FFFFFF; padding: 24px 32px; border-radius: 12px; 
            text-decoration: none; color: inherit; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.02);
            transition: all 0.2s ease;
            border: 1px solid rgba(0,0,0,0.04);
        }}
        .issue-card:hover {{ 
            transform: translateY(-4px); 
            box-shadow: 0 12px 24px rgba(0,0,0,0.06); 
            border-color: rgba(200,75,49,0.3);
        }}
        .issue-date {{ font-size: 0.8rem; color: #8C7A6B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }}
        .issue-title {{ font-family: 'Fraunces', serif; font-size: 1.4rem; font-weight: 700; color: #1A1A1A; }}
        .issue-arrow {{ color: #C84B31; font-size: 1.5rem; transition: transform 0.2s; }}
        .issue-card:hover .issue-arrow {{ transform: translateX(8px); }}
        
        @media (max-width: 600px) {{
            .issue-card {{ flex-direction: column; align-items: flex-start; gap: 12px; padding: 20px; }}
            .issue-arrow {{ align-self: flex-end; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="subtitle">Issue Archive</div>
            <h1>Morning Edition</h1>
            <div class="rule"></div>
            <p style="color: #666;">A curated bilingual daily digest for engineers and builders.</p>
        </header>

        <div class="archive-grid">
            {items_html if items_html else "<p style='text-align:center; color:#8C7A6B;'>No issues found yet. Check back tomorrow!</p>"}
        </div>
        
        <footer style="margin-top: 80px; text-align: center; font-size: 0.8rem; color: #B0A090;">
            Automatically generated • Powering {len(html_files)} issues
        </footer>
    </div>
</body>
</html>
'''

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    print("✅ Archive updated: index.html generated.")

if __name__ == "__main__":
    generate_index()
