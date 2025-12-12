import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print(f"Python Executable: {sys.executable}")
print("Checking imports...")

try:
    import torch
    print(f"✅ torch imported: version {torch.__version__}")
except ImportError as e:
    print(f"❌ torch import failed: {e}")

try:
    import transformers
    from transformers import CLIPProcessor, CLIPModel
    print(f"✅ transformers imported: version {transformers.__version__}")
except ImportError as e:
    print(f"❌ transformers import failed: {e}")

try:
    from backend import audit
    print(f"✅ backend.audit imported")
    print(f"audit.HAS_CLIP = {audit.HAS_CLIP}")
    
    if audit.HAS_CLIP:
        print("Attempting to load CLIP model...")
        model, processor = audit.get_clip_model()
        if model:
            print("✅ CLIP model loaded successfully")
        else:
            print("❌ get_clip_model returned None")
    else:
        print("⚠️ audit.HAS_CLIP is False, audit logic will skip CLIP.")

except Exception as e:
    print(f"❌ Unexpected error during audit check: {e}")
