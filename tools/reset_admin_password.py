
import sys
import os
import sqlite3
import bcrypt

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.config import DB_PATH

def reset_password(username="admin", new_password="password123"):
    print(f"Target Database: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ Database not found!")
        return

    # Generate new hash using explicit bcrypt (same logic as new auth.py)
    # Ensure bytes for bcrypt
    pwd_bytes = new_password.encode('utf-8')
    salt = bcrypt.gensalt()
    new_hash = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
    
    print(f"Resetting password for user: {username}")
    print(f"New Password: {new_password}")
    print(f"New Hash: {new_hash[:10]}...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check user exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        row = c.fetchone()
        
        if not row:
            print(f"❌ User '{username}' not found!")
            # Try to find any admin
            c.execute("SELECT username FROM users WHERE is_admin = 1 LIMIT 1")
            admin_row = c.fetchone()
            if admin_row:
                print(f"Did you mean: {admin_row[0]}?")
            else:
                print("No admin users found.")
                
            choice = input(f"Do you want to create user '{username}' as admin? (y/n): ")
            if choice.lower() == 'y':
                c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)", 
                          (username, new_hash))
                conn.commit()
                print(f"✅ Created new admin user: {username}")
            return

        # Update password
        c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))
        conn.commit()
        
        if c.rowcount > 0:
            print("✅ Password reset successfully!")
        else:
            print("⚠️ No changes made (maybe user not found?)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reset user password")
    parser.add_argument("username", nargs="?", default="admin", help="Username to reset")
    parser.add_argument("password", nargs="?", default="admin123", help="New password")
    
    args = parser.parse_args()
    reset_password(args.username, args.password)
