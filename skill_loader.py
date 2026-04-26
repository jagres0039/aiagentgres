import os
import re

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

def parse_skill_md(content: str) -> dict:
    """Parse SKILL.md dengan YAML frontmatter"""
    metadata = {}
    body = content

    if content.startswith('---'):
        try:
            end = content.find('---', 3)
            if end != -1:
                yaml_str = content[3:end].strip()
                # Parse YAML manual tanpa library
                for line in yaml_str.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('-'):
                        key, _, val = line.partition(':')
                        metadata[key.strip()] = val.strip()
                    elif line.startswith('- ') and 'triggers' not in metadata:
                        pass

                # Parse triggers khusus
                triggers = []
                in_triggers = False
                for line in yaml_str.split('\n'):
                    if 'triggers:' in line:
                        in_triggers = True
                        continue
                    if in_triggers:
                        if line.strip().startswith('- '):
                            triggers.append(line.strip()[2:].strip())
                        elif line.strip() and not line.startswith(' '):
                            in_triggers = False
                if triggers:
                    metadata['triggers'] = triggers

                # Parse priority
                for line in yaml_str.split('\n'):
                    if line.strip().startswith('priority:'):
                        try:
                            metadata['priority'] = int(line.split(':')[1].strip())
                        except:
                            metadata['priority'] = 5

                body = content[end+3:].strip()
        except:
            pass

    return metadata, body

def load_all_skills() -> list:
    skills = []
    if not os.path.exists(SKILLS_DIR):
        os.makedirs(SKILLS_DIR)
        return skills

    for skill_name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
        if os.path.exists(skill_path):
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata, body = parse_skill_md(content)

            skills.append({
                'name': skill_name,
                'content': content,
                'body': body,
                'metadata': metadata,
                'path': os.path.join(SKILLS_DIR, skill_name),
                'triggers': metadata.get('triggers', []),
                'description': metadata.get('description', ''),
                'priority': metadata.get('priority', 5),
            })

    skills.sort(key=lambda x: x.get('priority', 5))
    return skills

def match_skill(user_message: str) -> str:
    """Cari skill yang paling cocok dengan request user"""
    
    # Exclude keyword yang bukan skill
    non_skill_keywords = [
        'buat excel', 'bikin excel', 'create excel',
        'buat word', 'bikin word', 'create word',
        'buat event', 'set reminder', 'jadwalin',
        'kirim email', 'cek inbox', 'baca email',
        'inget ini', 'lupain', 'lihat memory',
        'buat skill', 'hapus skill', 'improve skill',
        'cariin', 'cari info', 'berita'
    ]
    
    user_lower = user_message.lower()
    for kw in non_skill_keywords:
        if kw in user_lower:
            return None
    
    skills = load_all_skills()

    best_match = None
    best_score = 0

    for skill in skills:
        score = 0
        triggers = skill.get('triggers', [])

        for trigger in triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in user_lower:
                score += 10
            else:
                trigger_words = trigger_lower.split()
                matched_words = sum(1 for w in trigger_words if w in user_lower)
                if len(trigger_words) > 0:
                    if matched_words == len(trigger_words):
                        score += 8
                    elif matched_words >= len(trigger_words) * 0.7:
                        score += 5

        skill_words = skill['name'].replace('_', ' ').split()
        for word in skill_words:
            if len(word) > 3 and word in user_lower:
                score += 2

        if score > best_score:
            best_score = score
            best_match = skill['name']

    return best_match if best_score >= 5 else None

def get_skills_prompt() -> str:
    """Generate prompt dari semua skill"""
    skills = load_all_skills()
    if not skills:
        return ""

    prompt = "SKILLS TERSEDIA — GUNAKAN JIKA TRIGGER COCOK:\n\n"
    for skill in skills:
        name = skill['name']
        desc = skill.get('description', '')
        triggers = skill.get('triggers', [])

        prompt += f"• SKILL: {name}\n"
        if desc:
            prompt += f"  Fungsi: {desc}\n"
        if triggers:
            prompt += f"  Trigger: {', '.join(triggers[:5])}\n"
        prompt += "\n"

    return prompt

def get_skill_names() -> list:
    skills = load_all_skills()
    return [s['name'] for s in skills]
