try:
    print("Attempting to import transformers...")
    from transformers import ChineseCLIPProcessor, ChineseCLIPModel
    print("Import successful.")

    print("Attempting to load model 'OFA-Sys/chinese-clip-vit-base-patch16'...")
    model = ChineseCLIPModel.from_pretrained("OFA-Sys/chinese-clip-vit-base-patch16")
    processor = ChineseCLIPProcessor.from_pretrained("OFA-Sys/chinese-clip-vit-base-patch16")
    print("Model loaded successfully.")
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()
