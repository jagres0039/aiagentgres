import subprocess
import os
import tempfile

SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills')

def execute_skill(skill_name: str, code: str) -> str:
    try:
        skill_dir = os.path.join(SKILLS_DIR, skill_name)

        if not os.path.exists(skill_dir):
            return f"❌ Skill '{skill_name}' tidak ditemukan."

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            dir=skill_dir,
            delete=False
        ) as f:
            f.write(code)
            temp_file = f.name

        result = subprocess.run(
            ['python3.11', temp_file],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=skill_dir
        )

        os.unlink(temp_file)

        if result.returncode == 0:
            return result.stdout.strip() or "✅ Skill berhasil dieksekusi."
        else:
            return f"❌ Error: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return "❌ Skill timeout (lebih dari 60 detik)"
    except Exception as e:
        return f"❌ Gagal eksekusi skill: {str(e)}"
