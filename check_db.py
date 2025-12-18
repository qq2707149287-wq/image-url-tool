
import sys
import os
import logging
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.db.users import create_user
from backend.db.connection import init_db, get_db_connection
from backend.config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_db():
    print(f"DB_PATH: {DB_PATH}")
    
    # 1. 检查 schema
    try:
        init_db()
        print("✅ Init DB success")
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info(users)")
            columns = c.fetchall()
            print("Users Table Schema:")
            for col in columns:
                print(col)
                
    except Exception as e:
        print(f"❌ Init DB failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 1.5 Test Password Hashing
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        print("\nTesting Password Hashing...")
        password = "test_password_123"
        hashed = pwd_context.hash(password)
        print(f"✅ Hashing success: {hashed[:10]}...")
        
        if pwd_context.verify(password, hashed):
            print("✅ Verify success")
        else:
            print("❌ Verify failed")
            
    except Exception as e:
        print(f"❌ Password Hashing failed: {e}")
        import traceback
        traceback.print_exc()
        # If hashing fails, we can't proceed with real user creation simulation
        return

    # 2. Try create user
    username = f"test_{os.urandom(4).hex()}"
    print(f"\nAttempting to create user: {username}")
    
    try:
        # Use the hashed password
        success = create_user(username, hashed)
        if success:
            print("✅ create_user returned True")
        else:
            print("❌ create_user returned False")
            
            # Manual Retry to catch exception
            print("   -> Retrying manually to catch exception...")
            with get_db_connection() as conn:
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password))
                    conn.commit()
                except Exception as e:
                    print(f"   ❌ Manual INSERT failed: {e}")
                    import traceback
                    traceback.print_exc()

    except Exception as e:
        print(f"❌ Script Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db()
