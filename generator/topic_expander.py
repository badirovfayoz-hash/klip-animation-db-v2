"""
TOPIC EXPANDER
Groq o'zi yangi mavzularni topadi va topics.py ga qo'shadi.
Bu tizim orqali mavzular 1,239 dan 20,000+ ga o'sadi.
"""

import os, sys, json, re
from pathlib import Path

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
MODEL = "llama-3.3-70b-versatile"

sys.path.insert(0, str(Path(__file__).parent))
from topics import ALL_TOPICS

EXPANSION_PROMPT = {
    'humans': """Generate 50 unique animation topic descriptions for stick figure humans.
Format: one topic per line, descriptive, action-focused.
Examples already used include: walking, running, sitting, writing.
Generate NEW ones not in that list. Focus on: specific emotions + actions,
professional activities, social situations, physical challenges, daily moments.
Output ONLY the list, no numbering, no explanation.""",

    'emotions': """Generate 50 unique emotional states and facial expressions for animation.
Format: one per line, vivid and specific.
Focus on: nuanced emotions, complex feelings, mixed states, cultural expressions.
Output ONLY the list.""",

    'animals': """Generate 50 unique animal behavior animations.
Format: "animal + specific action" per line.
Include: insects, sea creatures, birds, mammals, reptiles.
Focus on: specific behaviors, interactions, survival actions.
Output ONLY the list.""",

    'nature': """Generate 50 unique nature phenomena for animation.
Format: one per line, specific and visual.
Include: weather, geology, plants, water, seasons, space.
Output ONLY the list.""",

    'objects': """Generate 50 unique object animations.
Format: "object + its movement/behavior" per line.
Include: technology, household, transport, symbols, tools.
Output ONLY the list.""",

    'backgrounds': """Generate 50 unique background scene descriptions.
Format: one per line, atmospheric and specific.
Include: urban, nature, interior, fantasy, historical, futuristic.
Output ONLY the list.""",

    'events': """Generate 50 unique life event animations.
Format: one per line, showing specific human moment.
Include: milestones, daily life, celebrations, challenges, work.
Output ONLY the list.""",

    'relationships': """Generate 50 unique relationship dynamic animations.
Format: showing specific interaction between people.
Include: family, friendship, romance, conflict, community.
Output ONLY the list.""",

    'abstract': """Generate 50 unique abstract concept visualizations.
Format: "concept + visual metaphor" per line.
Include: psychology, philosophy, social dynamics, growth.
Output ONLY the list.""",
}

import urllib.request

def call_groq_for_topics(category):
    """Groq dan yangi mavzular oladi."""
    prompt = EXPANSION_PROMPT.get(category, f"Generate 50 unique {category} animation topics.")
    
    # Mavjud mavzularning namunasini qo'shish
    existing_sample = list(ALL_TOPICS.get(category, []))[:20]
    if existing_sample:
        sample_text = '\n'.join(f"- {t}" for t in existing_sample[:10])
        prompt += f"\n\nAlready have these (don't repeat):\n{sample_text}"
    
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
        "temperature": 0.9,  # Yuqori temperature = ko'proq xilma-xillik
        "messages": [
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
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        return data['choices'][0]['message']['content'].strip()


def parse_topics_from_response(text):
    """Groq javobidan mavzularni ajratib oladi."""
    lines = text.split('\n')
    topics = []
    
    for line in lines:
        # Raqam, tire, yulduzcha kabi prefixlarni olib tashlash
        clean = re.sub(r'^[\d\.\-\*\•\◦]+\s*', '', line.strip())
        clean = clean.strip('"\'')
        
        # Juda qisqa yoki uzun mavzularni o'tkazib yuborish
        if 5 < len(clean) < 100:
            topics.append(clean)
    
    return topics


def save_new_topics(category, new_topics):
    """Yangi mavzularni topics_expanded.py ga saqlaydi."""
    expanded_file = Path(__file__).parent / 'topics_expanded.py'
    
    # Mavjud expanded topiclarni o'qish
    existing_expanded = {}
    if expanded_file.exists():
        try:
            namespace = {}
            exec(expanded_file.read_text(), namespace)
            existing_expanded = namespace.get('EXPANDED_TOPICS', {})
        except:
            pass
    
    if category not in existing_expanded:
        existing_expanded[category] = []
    
    # Mavjud barcha topiclar (original + expanded)
    all_existing = set(ALL_TOPICS.get(category, [])) | set(existing_expanded.get(category, []))
    
    # Yangilarini filtrlash
    truly_new = [t for t in new_topics if t not in all_existing]
    existing_expanded[category].extend(truly_new)
    
    # Faylga yozish
    lines = ['"""', 'AUTO-GENERATED EXPANDED TOPICS', 'Do not edit manually', '"""', '']
    lines.append('EXPANDED_TOPICS = {')
    for cat, topics in existing_expanded.items():
        lines.append(f'    "{cat}": [')
        for topic in topics:
            escaped = topic.replace('"', '\\"')
            lines.append(f'        "{escaped}",')
        lines.append('    ],')
    lines.append('}')
    
    expanded_file.write_text('\n'.join(lines), encoding='utf-8')
    return len(truly_new)


def get_all_topics_combined():
    """Original + expanded topiclarni birlashtiradi."""
    expanded_file = Path(__file__).parent / 'topics_expanded.py'
    
    combined = {cat: list(topics) for cat, topics in ALL_TOPICS.items()}
    
    if expanded_file.exists():
        try:
            namespace = {}
            exec(expanded_file.read_text(), namespace)
            expanded = namespace.get('EXPANDED_TOPICS', {})
            for cat, topics in expanded.items():
                if cat in combined:
                    # Dublikatlarni oldini olish
                    existing = set(combined[cat])
                    new = [t for t in topics if t not in existing]
                    combined[cat].extend(new)
        except Exception as e:
            print(f"Expanded topics o'qishda xato: {e}")
    
    return combined


def expand_all_categories(topics_per_category=50):
    """Barcha kategoriyalar uchun yangi mavzular yaratadi."""
    if not GROQ_API_KEY:
        print("GROQ_API_KEY yo'q!")
        return
    
    import time
    total_new = 0
    
    for category in ALL_TOPICS:
        print(f"  {category}: yangi mavzular yaratilmoqda...")
        try:
            raw = call_groq_for_topics(category)
            new_topics = parse_topics_from_response(raw)
            added = save_new_topics(category, new_topics)
            print(f"    +{added} yangi mavzu")
            total_new += added
            time.sleep(2)  # Rate limit
        except Exception as e:
            print(f"    Xato: {e}")
    
    print(f"\nJami yangi mavzular: {total_new}")
    return total_new


if __name__ == '__main__':
    print("Topic Expander ishlamoqda...")
    combined = get_all_topics_combined()
    total = sum(len(v) for v in combined.values())
    print(f"Hozirgi jami: {total}")
    
    if total < 20000:
        print(f"Kengaytirilmoqda... (maqsad: 20,000)")
        expand_all_categories()
        combined = get_all_topics_combined()
        total = sum(len(v) for v in combined.values())
        print(f"Yangi jami: {total}")
