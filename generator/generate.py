"""
KLIP ANIMATION DB v2 — GENERATOR
Groq API bilan 24/7 ishlaydigan animatsiya generator.
Har ishga tushganda: Groq limitini maksimal ishlatadi.
Maqsad: 20,000+ Drama Farm uslubidagi Canvas 2D animatsiyalar.
"""

import os, sys, json, re, time, hashlib, subprocess
from pathlib import Path
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
DB_DIR = Path(__file__).parent.parent / 'db'
INDEX_FILE = DB_DIR / 'index.json'
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '100'))  # Har run'da 100 ta
MODEL = "llama-3.3-70b-versatile"

# Groq rate limits:
# Free tier: 14,400 requests/day, 30 req/min
DELAY_BETWEEN_REQUESTS = 2.1  # 30 req/min = 1 req/2 soniya

# ── SYSTEM PROMPT ────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Canvas 2D animation expert writing functions for "Drama Farm" style.

STYLE RULES (MUST FOLLOW):
- Background: beige/cream (#f5f0e8) or dark (#1a1a2e) colors
- Outlines: black, lineWidth 3-5 (bold, hand-drawn feel)
- Characters: stick figures with round heads, geometric bodies
- Colors: rich greens (#3d7a5c), warm yellows (#f5c842), deep blues
- Feeling: like hand-drawn whiteboard animation

FUNCTION FORMAT (EXACT):
function draw(ctx, t, W, H) {
  // t = time in seconds (use Math.sin/cos for loops)
  // W = 1280, H = 720
  ctx.save();
  
  // 1. Background
  ctx.fillStyle = '#f5f0e8';
  ctx.fillRect(0, 0, W, H);
  
  // 2. Animation elements (use t for motion)
  
  ctx.restore();
}

ANIMATION RULES:
- Use Math.sin(t), Math.cos(t) for smooth loops
- Always ctx.save() at start, ctx.restore() at end
- Center important elements at W/2, H/2
- Make it expressive and clear
- No external resources, pure canvas only
- Animation must clearly show the described action/emotion
- Write ONLY the function, nothing else"""


# ── IMPORT TOPICS ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from topics import ALL_TOPICS
    from topic_expander import get_all_topics_combined, expand_all_categories
    USE_EXPANDED = True
except ImportError:
    from topics import ALL_TOPICS
    USE_EXPANDED = False
    print("⚠️  topic_expander yo'q — faqat asosiy mavzular")


# ── GROQ API CALL ────────────────────────────────────────────────
import urllib.request, urllib.error

def call_groq(topic, category):
    """Groq API ga so'rov yuboradi."""
    
    # Kategoriyaga qarab qo'shimcha context
    context = {
        'humans': "Draw a stick figure person performing this action. Show clear body movement.",
        'emotions': "Draw a stick figure face/body clearly showing this emotion. Exaggerate for clarity.",
        'animals': "Draw this animal performing this action in Drama Farm stick style.",
        'nature': "Draw this nature scene or phenomenon. Include movement with Math.sin(t).",
        'objects': "Draw this object with its characteristic movement or behavior.",
        'backgrounds': "Draw this background scene with atmospheric details and subtle animation.",
        'events': "Draw stick figures experiencing this life event. Show emotion clearly.",
        'relationships': "Draw stick figures showing this relationship dynamic.",
        'abstract': "Visualize this abstract concept with simple geometric shapes and metaphors.",
    }.get(category, "Draw this concept clearly.")
    
    prompt = f"""Animation topic: "{topic}"
Category: {category}

{context}

Write only the draw(ctx, t, W, H) function. Drama Farm style. No explanation."""
    
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    }).encode()
    
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }
    )
    
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())
        return data['choices'][0]['message']['content'].strip()


def extract_js_function(raw):
    """JS funksiyasini javobdan ajratib oladi."""
    # Markdown code block olib tashlash
    raw = re.sub(r'```(?:javascript|js)?\n?', '', raw)
    raw = re.sub(r'```', '', raw).strip()
    
    # function draw( dan boshlaydigan joyni topish
    match = re.search(r'function\s+draw\s*\(', raw)
    if not match:
        return None
    
    start = match.start()
    depth = 0
    i = start
    while i < len(raw):
        if raw[i] == '{':
            depth += 1
        elif raw[i] == '}':
            depth -= 1
            if depth == 0:
                return raw[start:i+1]
        i += 1
    return None


def validate_js(code):
    """Node.js bilan JS kodini tekshiradi."""
    test = f"""
{code}
if (typeof draw !== 'function') throw new Error('draw is not a function');
// Quick syntax check passed
"""
    try:
        result = subprocess.run(
            ['node', '-e', test],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        # Node yo'q bo'lsa — sintaktik tekshirish qilmaymiz
        return 'function draw' in code and 'ctx' in code


def make_id(category, topic):
    """Unique ID yaratadi."""
    clean = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')[:60]
    return f"{category}_{clean}"


def get_existing_topics(category):
    """Allaqachon yaratilgan topiclarni qaytaradi."""
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
    """Animatsiyani JSON fayliga saqlaydi."""
    cat_dir = DB_DIR / anim['category']
    cat_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = cat_dir / f"{anim['id']}.json"
    filepath.write_text(
        json.dumps(anim, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    return filepath


def rebuild_index():
    """Barcha animatsiyalardan index.json yaratadi."""
    index = {
        "version": "2.0",
        "generated": datetime.now().isoformat(),
        "total": 0,
        "categories": {}
    }
    
    for category in ALL_TOPICS:
        cat_dir = DB_DIR / category
        if not cat_dir.exists():
            index['categories'][category] = []
            continue
        
        items = []
        for f in sorted(cat_dir.glob('*.json')):
            try:
                data = json.loads(f.read_text())
                items.append({
                    "id": data['id'],
                    "topic": data['topic'],
                    "tags": data.get('tags', []),
                    "file": f"{category}/{f.name}",
                    "category": category
                })
            except:
                pass
        
        index['categories'][category] = items
        print(f"  {category:15s}: {len(items):4d} animatsiya")
    
    index['total'] = sum(len(v) for v in index['categories'].values())
    INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )
    return index['total']


def get_pending_topics():
    """Yaratilmagan topiclar ro'yxatini qaytaradi."""
    pending = []
    
    for category, topics in ALL_TOPICS.items():
        existing = get_existing_topics(category)
        for topic in topics:
            if topic not in existing:
                pending.append((category, topic))
    
    return pending


# ── MAIN ─────────────────────────────────────────────────────────

def main():
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY environment variable yo'q!")
        sys.exit(1)
    
    print("=" * 60)
    print("KLIP ANIMATION DB v2 — Groq Generator")
    print(f"Model: {MODEL}, Batch: {BATCH_SIZE}")
    print("=" * 60)
    
    # Mavzularni olish (original + expanded)
    if USE_EXPANDED:
        combined = get_all_topics_combined()
        total_topics = sum(len(v) for v in combined.values())
        print(f"\nMavzular (original + expanded): {total_topics}")
        
        # Agar 5,000 dan kam bo'lsa — yangilarini yaratamiz
        if total_topics < 5000:
            print("📝 Yangi mavzular yaratilmoqda...")
            expand_all_categories(50)
            combined = get_all_topics_combined()
            total_topics = sum(len(v) for v in combined.values())
            print(f"Yangilangan jami: {total_topics}")
    else:
        combined = ALL_TOPICS
        total_topics = sum(len(v) for v in combined.values())
        print(f"\nMavzular: {total_topics}")
    
    # Pending topiclar
    def get_all_pending():
        result = []
        for category, topics in combined.items():
            existing = get_existing_topics(category)
            for topic in topics:
                if topic not in existing:
                    result.append((category, topic))
        return result
    
    pending = get_all_pending()
    existing_count = total_topics - len(pending)
    
    print(f"Allaqachon yaratilgan: {existing_count}")
    print(f"Qolgan: {len(pending)}")
    print(f"Hozir yaratiladi: {min(BATCH_SIZE, len(pending))}")
    print()
    
    if not pending:
        print("✅ Barcha animatsiyalar yaratilgan!")
        rebuild_index()
        return
    
    # Tasodifiy tartibda (xilma-xillik uchun)
    import random
    random.shuffle(pending)
    
    generated = 0
    errors = 0
    start_time = time.time()
    
    for category, topic in pending[:BATCH_SIZE]:
        if generated >= BATCH_SIZE:
            break
        
        print(f"[{generated+1:3d}/{min(BATCH_SIZE, len(pending))}] "
              f"{category:12s} | {topic[:50]}...", end=' ', flush=True)
        
        try:
            raw = call_groq(topic, category)
            code = extract_js_function(raw)
            
            if not code:
                print("⚠️  SKIP")
                errors += 1
                time.sleep(DELAY_BETWEEN_REQUESTS)
                continue
            
            if not validate_js(code):
                print("⚠️  JS XATO")
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
            print(f"✅ ({len(code)} chars)")
            generated += 1
            
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"⏳ Rate limit! 65s...")
                time.sleep(65)
                try:
                    raw = call_groq(topic, category)
                    code = extract_js_function(raw)
                    if code:
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
                        print("✅ Retry!")
                        generated += 1
                except:
                    errors += 1
            else:
                print(f"❌ HTTP {e.code}")
                errors += 1
        except Exception as e:
            print(f"❌ {str(e)[:40]}")
            errors += 1
            time.sleep(2)
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ Yaratildi: {generated} | ❌ Xato: {errors} | ⏱ {elapsed:.0f}s")
    
    print("\n📑 Index yangilanmoqda...")
    total = rebuild_index()
    print(f"✅ Jami: {total} animatsiya")


if __name__ == '__main__':
    main()
