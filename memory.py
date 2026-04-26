import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabel conversation history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabel long term memory (fakta tentang user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, key)
        )
    ''')
    
    # Tabel user preferences
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            UNIQUE(user_id, key)
        )
    ''')
    
    conn.commit()
    conn.close()

# Inisialisasi DB saat import
init_db()

MAX_HISTORY = 20

def add_message(user_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)',
        (user_id, role, content)
    )
    
    # Hapus history lama kalau udah lebih dari MAX_HISTORY
    cursor.execute('''
        DELETE FROM conversations 
        WHERE user_id = ? AND id NOT IN (
            SELECT id FROM conversations 
            WHERE user_id = ? 
            ORDER BY id DESC 
            LIMIT ?
        )
    ''', (user_id, user_id, MAX_HISTORY))
    
    conn.commit()
    conn.close()

def get_history(user_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, content FROM conversations 
        WHERE user_id = ? 
        ORDER BY id DESC 
        LIMIT ?
    ''', (user_id, MAX_HISTORY))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Balik urutan biar chronological
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

def clear_history(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def save_memory(user_id: int, key: str, value: str):
    """Simpan fakta penting tentang user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO long_term_memory (user_id, key, value, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, key, value))
    conn.commit()
    conn.close()

def get_memory(user_id: int) -> dict:
    """Ambil semua memory tentang user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT key, value FROM long_term_memory WHERE user_id = ?',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def get_memory_prompt(user_id: int) -> str:
    """Generate prompt dari long term memory"""
    memories = get_memory(user_id)
    if not memories:
        return ""
    
    prompt = "Yang lo tau tentang user ini:\n"
    for key, value in memories.items():
        prompt += f"- {key}: {value}\n"
    return prompt

def save_preference(user_id: int, key: str, value: str):
    """Simpan preferensi user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO preferences (user_id, key, value)
        VALUES (?, ?, ?)
    ''', (user_id, key, value))
    conn.commit()
    conn.close()

def get_preferences(user_id: int) -> dict:
    """Ambil semua preferensi user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT key, value FROM preferences WHERE user_id = ?',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def delete_memory(user_id: int, key: str):
    """Hapus memory tertentu"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM long_term_memory WHERE user_id = ? AND key = ?',
        (user_id, key)
    )
    conn.commit()
    conn.close()

def get_all_user_ids() -> list:
    """Ambil semua user ID yang pernah chat"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM conversations')
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def get_all_memories_text(user_id: int) -> str:
    """Tampilkan semua memory dalam format teks"""
    memories = get_memory(user_id)
    prefs = get_preferences(user_id)

    if not memories and not prefs:
        return "Belum ada memory yang tersimpan."

    output = "🧠 Memory lo:\n━━━━━━━━━━━━━━━\n"

    if memories:
        output += "\n📌 Fakta tentang lo:\n"
        for key, value in memories.items():
            output += f"• {key}: {value}\n"

    if prefs:
        output += "\n⚙️ Preferensi lo:\n"
        for key, value in prefs.items():
            output += f"• {key}: {value}\n"

    return output
