import os
import sys
import sqlite3
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import save_to_db, get_history_list, delete_history_items, clear_all_history, init_db, DB_PATH

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_delete_issue():
    print("--- Starting Deletion Issue Test ---")
    
    device_id = "test_delete_user"
    
    # Mock image data
    image_private = {
        "url": "http://example.com/private.png",
        "filename": "private.png",
        "hash": "private_hash",
        "service": "local",
        "width": 100,
        "height": 100,
        "size": 1024,
        "content_type": "image/png"
    }
    
    image_shared = {
        "url": "http://example.com/shared.png",
        "filename": "shared.png",
        "hash": "shared_hash",
        "service": "local",
        "width": 100,
        "height": 100,
        "size": 1024,
        "content_type": "image/png"
    }
    
    # Initialize and clean
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM history WHERE device_id = ?", (device_id,))
        conn.commit()
        
    # 1. Test Individual Delete of Shared Image
    print("\n1. Testing Individual Delete of Shared Image...")
    save_to_db(image_shared, device_id=device_id, is_shared=True)
    
    # Get ID
    history = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    if not history['data']:
        print("❌ Setup failed: No shared image found.")
        return
        
    shared_id = history['data'][0]['id']
    print(f"   -> Created shared image with ID: {shared_id}")
    
    # Delete it
    result = delete_history_items([shared_id], device_id=device_id)
    print(f"   -> Delete result: {result}")
    
    # Verify
    history_after = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    found = any(item['id'] == shared_id for item in history_after['data'])
    if found:
        print("❌ FAILED: Shared image was NOT deleted.")
    else:
        print("✅ PASSED: Shared image was deleted successfully.")

    # 2. Test Clear All (Mode Specific)
    print("\n2. Testing Clear All (Mode Specific)...")
    # Create one private and one shared
    save_to_db(image_private, device_id=device_id, is_shared=False)
    save_to_db(image_shared, device_id=device_id, is_shared=True)
    
    print("   -> Created 1 private and 1 shared image.")
    
    # Clear Private Only
    print("   -> Clearing PRIVATE history...")
    clear_all_history(device_id=device_id, view_mode="private")
    
    # Verify
    history_private = get_history_list(view_mode="private", device_id=device_id)
    history_shared = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    
    count_private = len(history_private['data'])
    count_shared = len(history_shared['data'])
    
    print(f"   -> Remaining Private: {count_private}")
    print(f"   -> Remaining Shared: {count_shared}")
    
    if count_private == 0 and count_shared == 1:
        print("✅ PASSED: 'Clear All (Private)' deleted only private images.")
    else:
        print("❌ FAILED: 'Clear All (Private)' did not work as expected.")

    # Clear Shared Only
    print("   -> Clearing SHARED history...")
    clear_all_history(device_id=device_id, view_mode="shared")
    
    history_shared_after = get_history_list(view_mode="shared", device_id=device_id, only_mine=True)
    count_shared_after = len(history_shared_after['data'])
    
    print(f"   -> Remaining Shared: {count_shared_after}")
    
    if count_shared_after == 0:
        print("✅ PASSED: 'Clear All (Shared)' deleted shared images.")
    else:
        print("❌ FAILED: 'Clear All (Shared)' did not work as expected.")

if __name__ == "__main__":
    test_delete_issue()
