"""
KLIP ANIMATION DB v2 — GENERATOR
Google Gemini API bilan 24/7 ishlaydigan animatsiya generator.
Kuniga 1500 bepul so'rov!
"""

import os, sys, json, re, time
from pathlib import Path
from datetime import datetime

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
DB_DIR = Path(__file__).parent.parent / 'db'
INDEX_FILE = DB_DIR / 'index.json'
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '50'))
MODEL = "gemini-2.0-flash"
DELAY_BETWEEN_REQUESTS = 10.0

SYSTEM_PROMPT = """You are a Canvas 2D animation expert writing functions for Drama Farm style.

STYLE RULES:
- Background: beige/cream (#f5f0e8)
- Outlines: black, lineWidth 3-5
- Characters: stick figures with round heads
- Feeling: hand-drawn whiteboard animation

FUNCTION FORMAT (write ONLY this):
function draw(ctx, t, W, H) {
  ctx.save();
  ctx.fillStyle = '#f5f0e8';
  ctx.fillRect(0, 0, W, H);
  // animation here using Math.sin(t)
  ctx.restore();
}

RULES:
- Use Math.sin(t), Math.cos(t) for smooth loops
- Always ctx.save() and ctx.restore()
- Write ONLY the function, nothing else"""

sys.path.insert(0, str(Path(__file__).parent))
from topics import ALL_TOPICS

import urllib.request, urllib.error

def call_gemini(topic, category):
    prompt = f'Animation topic: "{topic}"\nCategory: {category}\nWrite only the draw(ctx, t, W, H) function. Drama Farm style. No explanation.'
    
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]
        }],
        "generationConfig": {
            "maxOutputTokens": 2000,
            "temperature": 0.7
        }
    }).encode()
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())
        return data['candidates'][0]['content']['parts'][0]['text'].strip()

def extract_js_function(raw):
    raw = re.sub(r'```(?:javascript|js)?\n?', '', raw)
    raw = re.sub(r'```', '', raw).strip()
    match = re.search(r'function\s+draw\s*\(', raw)
    if not match:
        return None
    start = match.start()
    depth = 0
    i = start
    while i < len(raw):
        if raw[i] == '{': depth += 1
        elif raw[i] == '}':
            depth -= 1
            if depth == 0:
                return raw[start:i+1]
        i += 1
    return None

def make_id(category, topic):
    clean = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')[:60]
    return f"{category}_{clean}"

def get_existing_topics(category):
    cat_dir = DB_DIR / category
    if not cat_dir.exists():
        return set()
    existing = set()
    for f in cat_dir.glob('*.json'):
        try:
            data = json.loads(f.read_text())
            existing.add(data.get('topic', ''))
        except:
            pass
    return existing

def save_animation(anim):
    cat_dir = DB_DIR / anim['category']
    cat_dir.mkdir(parents=True, exist_ok=True)
    filepath = cat_dir / f"{anim['id']}.json"
    filepath.write_text(json.dumps(anim, indent=2, ensure_ascii=False), encoding='utf-8')

def rebuild_index():
    index = {"version": "2.0", "generated": datetime.now().isoformat(), "total": 0, "categories": {}}
    for category in ALL_TOPICS:
        cat_dir = DB_DIR / category
        if not cat_dir.exists():
            index['categories'][category] = []
            continue
        items = []
        for f in sorted(cat_dir.glob('*.json')):
            try:
                data = json.loads(f.read_text())
                items.append({"id": data['id'], "topic": data['topic'], "file": f"{category}/{f.name}", "category": category})
            except:
                pass
        index['categories'][category] = items
        print(f"  {category}: {len(items)}")
    index['total'] = sum(len(v) for v in index['categories'].values())
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    return index['total']

def main():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY yo'q!")
        sys.exit(1)
    
    print("=" * 50)
    print("KLIP ANIMATION DB v2 — Gemini Generator")
    print(f"Model: {MODEL}, Batch: {BATCH_SIZE}")
    print("=" * 50)
    
    pending = []
    for category, topics in ALL_TOPICS.items():
        existing = get_existing_topics(category)
        for topic in topics:
            if topic not in existing:
                pending.append((category, topic))
    
    print(f"Qolgan: {len(pending)}")
    print(f"Hozir yaratiladi: {min(BATCH_SIZE, len(pending))}")
    
    if not pending:
        print("Barcha animatsiyalar tayyor!")
        rebuild_index()
        return
    
    import random
    random.shuffle(pending)
    
    generated = 0
    errors = 0
    
    for category, topic in pending[:BATCH_SIZE]:
        print(f"[{generated+1}/{min(BATCH_SIZE, len(pending))}] {category} | {topic[:40]}...", end=' ', flush=True)
        try:
            raw = call_gemini(topic, category)
            code = extract_js_function(raw)
            if not code:
                print("SKIP")
                errors += 1
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue
            anim = {
                "id": make_id(category, topic),
                "category": category,
                "topic": topic,
                "tags": topic.lower().split()[:10],
                "created": datetime.now().isoformat(),
                "model": MODEL,
                "draw": code
            }
            save_animation(anim)
            print(f"OK ({len(code)} chars)")
            generated += 1
        except Exception as e:
            print(f"XATO: {str(e)[:60]}")
            errors += 1
            time.sleep(5)
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    print(f"\nYaratildi: {generated} | Xato: {errors}")
    total = rebuild_index()
    print(f"Jami: {total} animatsiya")

if __name__ == '__main__':
    main()
