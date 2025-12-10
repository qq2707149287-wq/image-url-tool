import os
import sys
import sqlite3
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import save_to_db, get_history_list, init_db, DB_PATH

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_consistency_issue():
    print("--- Starting Reproduction Test ---")
    
    # Use a specific device_id for testing
    device_id = "test_device_123"
    
    # Mock image data
    image_data = {
        "url": "http://example.com/image.png",
        "filename": "image.png",
        "hash": "abc123hash",
        "service": "local",
        "width": 100,
        "height": 100,
        "size": 1024,
        "content_type": "image/png"
    }
    
    # Ensure DB is initialized
    init_db()
    
    # Clean up previous test data
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM history WHERE device_id = ?", (device_id,))
        conn.commit()
        
    print("1. Uploading in SHARED mode...")
    save_to_db(image_data, device_id=device_id, is_shared=True)
    
    # Check shared history
    history = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    found_shared = any(item['hash'] == image_data['hash'] for item in history['data'])
    print(f"   -> Found in Shared History: {found_shared}")
    
    if not found_shared:
        print("❌ Failed Step 1: Image not found in shared history immediately after upload.")
        return

    print("2. Uploading same image in PRIVATE mode...")
    save_to_db(image_data, device_id=device_id, is_shared=False)
    
    # Check private history
    history_private = get_history_list(view_mode="private", device_id=device_id)
    found_private = any(item['hash'] == image_data['hash'] for item in history_private['data'])
    print(f"   -> Found in Private History: {found_private}")
    
    # Check shared history AGAIN
    history_shared_again = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    found_shared_again = any(item['hash'] == image_data['hash'] for item in history_shared_again['data'])
    print(f"   -> Found in Shared History (after private upload): {found_shared_again}")
    
    if found_private and not found_shared_again:
        print("✅ REPRODUCED: Image disappeared from Shared History after Private upload.")
    elif found_private and found_shared_again:
        print("❌ NOT REPRODUCED: Image still exists in both histories (Issue might be already fixed or logic differs).")
    else:
        print("❌ SOMETHING ELSE HAPPENED.")

if __name__ == "__main__":
    test_consistency_issue()
