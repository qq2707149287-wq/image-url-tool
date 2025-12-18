
import logging
import traceback

logging.basicConfig(level=logging.INFO)

print("Starting bcrypt check...")

try:
    from passlib.context import CryptContext
    import bcrypt
    print(f"Bcrypt version: {bcrypt.__version__}")
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    password = "test_password_123"
    print(f"Hashing password: '{password}' (len={len(password)})")
    
    hashed = pwd_context.hash(password)
    print(f"✅ Hashing result: {hashed}")
    
except Exception as e:
    print("❌ Passlib Error occurred:")
    # traceback.print_exc()

print("\n--- Testing Direct Bcrypt ---")
try:
    import bcrypt
    msg = b"test_password_123"
    salt = bcrypt.gensalt()
    hash_res = bcrypt.hashpw(msg, salt)
    print(f"✅ Direct Bcrypt success: {hash_res}")
except Exception as e:
    print(f"❌ Direct Bcrypt failed: {e}")
    traceback.print_exc()
