
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import DB_PATH

def inspect_users():
    print(f"Checking DB at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ DB file not found!")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, username, is_admin, password_hash FROM users")
        users = c.fetchall()
        
        print(f"\nFound {len(users)} users:")
        print("-" * 80)
        print(f"{'ID':<5} {'Username':<20} {'Is Admin':<10} {'Password Hash (Prefix)'}")
        print("-" * 80)
        
        for u in users:
            uid, name, is_admin, pwd_hash = u
            # Show prefix and length of hash to determine type
            hash_display = pwd_hash[:10] + "..." if pwd_hash else "None"
            print(f"{uid:<5} {name:<20} {is_admin:<10} {hash_display} (len={len(pwd_hash) if pwd_hash else 0})")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    inspect_users()
