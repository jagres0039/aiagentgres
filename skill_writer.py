import os

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from paths import SKILLS_DIR as _SKILLS_DIR

SKILLS_DIR = str(_SKILLS_DIR)
client = Groq(api_key=GROQ_API_KEY)

def write_skill(skill_name: str, description: str) -> str:
    try:
        skill_name = skill_name.lower().strip().replace(" ", "_")

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """Kamu adalah expert Python developer yang nulis skill untuk AI agent.
Tulis SKILL.md yang berisi deskripsi, trigger, dan kode Python lengkap.

Format wajib:
## Skill: [nama]

### Deskripsi
[deskripsi]

### Trigger
[kapan dipakai]

### Cara Pakai
Balas HANYA dengan format:
SKILL: [nama_skill]
CODE:
[kode python lengkap]

Pastiin kode:
- Lengkap dan bisa langsung dijalankan
- Pakai try/except untuk error handling
- Print output yang informatif
- Gunakan library standar atau requests saja"""
                },
                {
                    "role": "user",
                    "content": f"Buatkan skill bernama '{skill_name}' untuk: {description}"
                }
            ],
            max_tokens=2048,
        )

        skill_content = response.choices[0].message.content.strip()

        skill_dir = os.path.join(SKILLS_DIR, skill_name)
        os.makedirs(skill_dir, exist_ok=True)

        skill_file = os.path.join(skill_dir, 'SKILL.md')
        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(skill_content)

        return f"✅ Skill '{skill_name}' berhasil dibuat!\n📁 Lokasi: {skill_file}\n\n📝 Preview:\n{skill_content[:500]}..."

    except Exception as e:
        return f"❌ Gagal buat skill: {str(e)}"

def list_skills() -> str:
    if not os.path.exists(SKILLS_DIR):
        return "Belum ada skill."

    skills = []
    for skill_name in os.listdir(SKILLS_DIR):
        skill_path = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')
        if os.path.exists(skill_path):
            skills.append(f"• {skill_name}")

    if not skills:
        return "Belum ada skill."

    return f"🧩 Skill yang tersedia ({len(skills)}):\n" + "\n".join(skills)

def delete_skill(skill_name: str) -> str:
    import shutil
    skill_name = skill_name.lower().strip().replace(" ", "_")
    skill_dir = os.path.join(SKILLS_DIR, skill_name)

    if not os.path.exists(skill_dir):
        return f"❌ Skill '{skill_name}' tidak ditemukan."

    shutil.rmtree(skill_dir)
    return f"🗑️ Skill '{skill_name}' berhasil dihapus."

def improve_skill(skill_name: str, improvement: str) -> str:
    skill_name = skill_name.lower().strip().replace(" ", "_")
    skill_path = os.path.join(SKILLS_DIR, skill_name, 'SKILL.md')

    if not os.path.exists(skill_path):
        return f"❌ Skill '{skill_name}' tidak ditemukan."

    with open(skill_path, 'r') as f:
        current_content = f.read()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Kamu expert Python developer. Improve skill yang ada sesuai permintaan. Jaga format SKILL.md yang sama."
                },
                {
                    "role": "user",
                    "content": f"Improve skill ini:\n\n{current_content}\n\nImprovement yang diminta: {improvement}"
                }
            ],
            max_tokens=2048,
        )

        improved_content = response.choices[0].message.content.strip()

        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(improved_content)

        return f"✅ Skill '{skill_name}' berhasil di-improve!\n\n📝 Preview:\n{improved_content[:500]}..."

    except Exception as e:
        return f"❌ Gagal improve skill: {str(e)}"
