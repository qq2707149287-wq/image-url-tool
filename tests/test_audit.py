import sys
import os
from PIL import Image
import io

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import audit

def test_safe_image():
    print("Testing Safe Image...", end="")
    # Create a blue image (safe)
    img = Image.new('RGB', (100, 100), color='blue')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    content = img_byte_arr.getvalue()
    
    result = audit.check_image_safety(content)
    if result['safe'] == True and result['score'] < 0.1:
        print(" PASS")
    else:
        print(f" FAIL (Score: {result['score']})")

def test_unsafe_image_simulation():
    print("Testing Unsafe Image...", end="")
    # Create an image with skin-like color (e.g. R=255, G=200, B=150)
    skin_color = (255, 200, 150) 
    img = Image.new('RGB', (100, 100), color=skin_color)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    content = img_byte_arr.getvalue()
    
    result = audit.check_image_safety(content)
    
    if result['safe'] == False and result['score'] > 0.8:
        print(" PASS")
    else:
        print(f" FAIL (Safe={result['safe']}, Score={result['score']})")

if __name__ == "__main__":
    try:
        test_safe_image()
        test_unsafe_image_simulation()
    except Exception as e:
        print(f"\nError: {e}")
