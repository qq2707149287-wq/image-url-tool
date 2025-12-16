import logging
import io
import sys
import os

# [FIX] 强制使用 HuggingFace 国内镜像，解决国内网络无法下载 AI 模型的问题
# 必须在导入 transformers 之前设置
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import tempfile
from PIL import Image
import numpy as np

# [优化] 延迟导入: 不要在文件开头导入 PyTorch/NudeNet/Transformers
# 否则会导致服务启动极慢，甚至在低内存服务器上直接 OOM
# from nudenet import NudeDetector
# from transformers ...

# 设置日志 (强制配置到标准输出，确保用户能看见)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# 参考地图路径 (用于台湾检测)
REFERENCE_MAP_PATH = os.path.join(os.path.dirname(__file__), "data", "reference_china_map.jpg")

# 全局模型单例
_nude_detector = None
# Chinese-CLIP (政治内容)
_chinese_clip_model = None
_chinese_clip_processor = None
# OpenAI CLIP (通用内容)
_openai_clip_model = None
_openai_clip_processor = None
# 参考地图缓存
_reference_map = None

UNSAFE_NUDENET_LABELS = {
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}

# [Safe] 白名单 (中文)
# 告诉 AI 哪些东西是安全的，防止误判
SAFE_LABELS = [
    "自然风景",
    "城市街道或建筑",
    "艺术画作或插画",
    "普通人像", 
    "政治人物或新闻照片",        # 对应 politicians
    "平面设计海报",             # 对应 poster
    "游戏截图或CG画面",         # 对应 video game
    "特效化妆或万圣节装扮",     # 对应 clown/costume
    "拼贴艺术或马赛克风格",     # [Fix] 防止拼图/马赛克被误判为色情
    "现代艺术或抽象画",         # [Fix] 增强艺术识别
    "像素画或网格图案",         # [Fix] 增强马赛克识别
    "人脸特写",                 # [Fix] 防止大脸特写被误判
    "美食",
    "可爱的动物",
    "世界地图或中国地图",        # 普通地图放行
    "中文新闻报道或媒体截图",    # [Fix] 防止新闻被误判为反华宣传
    "社会新闻事件报道",          # [Fix] 社会新闻
    "电影或电视剧截图",          # [Fix] 影视内容
    "视频封面或缩略图"           # [Fix] 视频内容
]

# ==================== Chinese-CLIP 标签 (中国政治内容) ====================
CHINESE_SAFE_LABELS = [
    "自然风景", "城市街道或建筑", "艺术画作或插画", "普通人像",
    "政治人物或新闻照片", "游戏截图或CG画面", "电影或电视剧截图",
    "地图", "标准世界地图", "国旗或外国旗帜",  # [Fix] 用通用"地图"替代具体描述
    "聊天记录或文字截图", "表情包或搞笑图片", "产品说明书或单据",
    "代码或程序界面", "手机或电脑屏幕", "汽车或交通工具",
    "美食或饮料", "可爱的动物", "家具或室内设计",
    "抽象背景或纹理", "体育运动或健身", "动漫或二次元图片"
]

CHINESE_UNSAFE_LABELS = [
    # "一张缺少台湾的错误中国地图",  # [已禁用] 改用模板匹配检测
    "台独港独藏独旗帜",     # 分裂主义旗帜
]

CHINESE_ALL_LABELS = CHINESE_SAFE_LABELS + CHINESE_UNSAFE_LABELS

# ==================== OpenAI CLIP 标签 (通用内容检测 - 英文) ====================
OPENAI_SAFE_LABELS = [
    "a natural landscape photo",
    "a video game screenshot",
    "a movie or TV show scene",
    "a news photo",
    "a normal portrait photo",
    "a food photo",
    "an art painting",
    "a national flag",
    "a world map",              
    "a map of national flags",
    "a meme or funny picture",
    "a screenshot of text or chat",
    "a receipt or document",
    "computer code or screen",
    "a car or vehicle",
    "a cat or dog",
    "a close-up of an object",
    "a sports photo",
    "an anime or cartoon image",
    "a logo or icon"
]

OPENAI_UNSAFE_LABELS = [
    "ISIS terrorist flag or propaganda",    # 恐怖组织旗帜/宣传
    "real beheading or execution video",    # 真实斩首/处决视频
    "illegal drug dealing scene",           # 毒品交易场景
    "bloody gore or dead body",             # 血腥/尸体
]

OPENAI_ALL_LABELS = OPENAI_SAFE_LABELS + OPENAI_UNSAFE_LABELS

def check_taiwan_region(image: Image.Image) -> dict:
    """
    检测中国地图是否包含台湾
    通过对比台湾区域和大陆区域的颜色来判断
    返回: {"is_map": bool, "has_taiwan": bool, "color_match": float}
    """
    global _reference_map
    
    try:
        # 加载参考地图
        if _reference_map is None:
            if os.path.exists(REFERENCE_MAP_PATH):
                _reference_map = Image.open(REFERENCE_MAP_PATH).convert("RGB")
                print(f"✅ [地图检测] 参考地图已加载", flush=True)
            else:
                print(f"⚠️ [地图检测] 参考地图不存在: {REFERENCE_MAP_PATH}", flush=True)
                return {"is_map": False, "has_taiwan": True, "color_match": 1.0}
        
        # 保持比例缩放到 800 宽度
        original_w, original_h = image.size
        scale = 800 / original_w
        new_h = int(original_h * scale)
        img_resized = image.convert("RGB").resize((800, new_h), Image.Resampling.LANCZOS)
        
        # 定义区域 (相对坐标，根据中国地图的标准比例)
        # 台湾区域: 右侧偏下 (大约在 x: 82%-92%, y: 55%-72%)
        taiwan_box = (
            int(800 * 0.82),      # 左
            int(new_h * 0.55),    # 上
            int(800 * 0.92),      # 右
            int(new_h * 0.72),    # 下
        )
        
        # 大陆区域: 中部 (作为参考陆地颜色)
        mainland_box = (
            int(800 * 0.45),      # 左
            int(new_h * 0.35),    # 上
            int(800 * 0.60),      # 右
            int(new_h * 0.50),    # 下
        )
        
        taiwan_region = img_resized.crop(taiwan_box)
        mainland_region = img_resized.crop(mainland_box)
        
        # 获取背景颜色 (左上角，通常是海洋/白色)
        background_box = (0, 0, 50, 50)
        background_region = img_resized.crop(background_box)
        
        # 计算平均颜色
        taiwan_arr = np.array(taiwan_region).astype(float)
        mainland_arr = np.array(mainland_region).astype(float)
        background_arr = np.array(background_region).astype(float)
        
        taiwan_avg_color = np.mean(taiwan_arr, axis=(0, 1))
        mainland_avg_color = np.mean(mainland_arr, axis=(0, 1))
        background_avg_color = np.mean(background_arr, axis=(0, 1))
        
        # 计算台湾与背景的颜色差异
        taiwan_vs_background = np.sqrt(np.sum((taiwan_avg_color - background_avg_color) ** 2))
        # 计算大陆与背景的颜色差异 (作为参考)
        mainland_vs_background = np.sqrt(np.sum((mainland_avg_color - background_avg_color) ** 2))
        
        # 检查图片是否像地图 
        img_gray = np.array(img_resized.convert("L"))
        light_ratio = np.mean(img_gray > 200) 
        is_likely_map = light_ratio > 0.20  # 降低阈值，适应彩色地图
        
        # 判断台湾是否存在:
        # 1. 台湾颜色要和背景不同 (差异 > 30)
        # 2. 如果大陆和背景差异很大，台湾也应该和背景有差异
        taiwan_brightness = float(np.mean(taiwan_arr))
        has_taiwan = taiwan_vs_background > 30  # 台湾颜色和背景差异要 > 30
        
        print(f"🗺️ [地图检测] 是地图: {is_likely_map}", flush=True)
        print(f"   背景颜色: {background_avg_color.astype(int)}", flush=True)
        print(f"   大陆颜色: {mainland_avg_color.astype(int)} (与背景差: {mainland_vs_background:.0f})", flush=True)
        print(f"   台湾颜色: {taiwan_avg_color.astype(int)} (与背景差: {taiwan_vs_background:.0f})", flush=True)
        print(f"   有台湾: {has_taiwan} (需要差异 > 30)", flush=True)
        
        return {
            "is_map": bool(is_likely_map),
            "has_taiwan": bool(has_taiwan),
            "color_match": float(taiwan_vs_background / 255.0),
            "taiwan_brightness": float(taiwan_brightness)
        }
        
    except Exception as e:
        print(f"❌ [地图检测] 错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return {"is_map": False, "has_taiwan": True, "color_match": 1.0}

def get_nude_detector():
    global _nude_detector
    if _nude_detector is None:
        print("⏳ [系统] 初始化 NudeNet...", flush=True)
        try:
            from nudenet import NudeDetector
            _nude_detector = NudeDetector()
        except ImportError as e:
            print(f"❌ [系统] NudeNet 导入失败: {e}", flush=True)
            return None
    return _nude_detector

def get_chinese_clip():
    """加载 Chinese-CLIP 用于中国政治内容检测"""
    global _chinese_clip_model, _chinese_clip_processor
    
    if _chinese_clip_model is None or _chinese_clip_processor is None:
        print("⏳ [系统] 初始化 Chinese-CLIP (阿里达摩院版)...", flush=True)
        try:
            import torch
            try:
                # 优先尝试官方推荐的专用类
                from transformers import ChineseCLIPProcessor, ChineseCLIPModel
                ModelClass = ChineseCLIPModel
                ProcessorClass = ChineseCLIPProcessor
            except ImportError:
                # 兼容旧版本 transformers：尝试使用 Auto 类
                print("⚠️ [系统] transformers 版本不支持 ChineseCLIPProcessor，尝试使用 AutoProcessor...", flush=True)
                from transformers import AutoProcessor, AutoModel
                ModelClass = AutoModel
                ProcessorClass = AutoProcessor

            model_id = "OFA-Sys/chinese-clip-vit-base-patch16"
            # [Fix] 使用临时变量，确保加载完全成功后再赋值给全局变量
            # [Fix 2] 添加 attn_implementation='eager' 解决 transformers 4.50+ 的 meta device bug
            model = ModelClass.from_pretrained(
                model_id, 
                low_cpu_mem_usage=False,
                attn_implementation="eager"  # 显式使用 eager attention，避免 SDPA meta bug
            )
            processor = ProcessorClass.from_pretrained(model_id)
            
            _chinese_clip_model = model
            _chinese_clip_processor = processor
            print("✅ [系统] Chinese-CLIP 加载完成 (中国政治内容检测)", flush=True)
        except Exception as e:
            # 降级处理：不影响主流程，只打印警告
            print(f"⚠️ [系统] Chinese-CLIP 加载失败: {e}", flush=True)
            print("   (将跳过中国政治内容检测，仅使用 OpenAI CLIP)", flush=True)
            # 确保全局变量重置为 None，防止部分加载
            _chinese_clip_model = None
            _chinese_clip_processor = None
            return None, None
    return _chinese_clip_model, _chinese_clip_processor

def get_openai_clip():
    """加载 OpenAI CLIP 用于通用内容检测 (暴力/恐怖等)"""
    global _openai_clip_model, _openai_clip_processor
        
    if _openai_clip_model is None or _openai_clip_processor is None:
        print("⏳ [系统] 初始化 OpenAI CLIP...", flush=True)
        try:
            # [Lazy Import]
            from transformers import CLIPProcessor, CLIPModel
            import torch

            model_id = "openai/clip-vit-base-patch32"
            # [FIX] 使用临时变量，防止部分加载导致全局状态不一致
            # 添加 device_map=None 防止 accelerate 自动将模型放到 meta device
            model = CLIPModel.from_pretrained(model_id, low_cpu_mem_usage=False, device_map=None)
            model.to('cpu') # 显式移动到 CPU
            processor = CLIPProcessor.from_pretrained(model_id)
            
            _openai_clip_model = model
            _openai_clip_processor = processor
            print("✅ [系统] OpenAI CLIP 加载完成 (通用内容检测)", flush=True)
        except Exception as e:
            print(f"❌ [系统] OpenAI CLIP 加载失败: {e}", flush=True)
            _openai_clip_model = None
            _openai_clip_processor = None
            return None, None
    return _openai_clip_model, _openai_clip_processor

def check_image_safety(content: bytes, threshold: float = 0.50) -> dict:
    # 强制打印，确保用户能看到
    print("\n🔍 [Audit] 开始新一轮图片审计 (Powered by NudeNet & CLIP & 地图检测)...", flush=True)
    
    # [FIX] 解决 check_image_safety 中使用 torch.no_grad() 但未导入 torch 的问题
    try:
        import torch
    except ImportError:
        print("❌ [系统] 无法导入 torch, AI 审核将受限", flush=True)

    result = {"safe": True, "score": 0.0, "reason": "Pass", "details": {}}
    
    # --- 0. 地图检测 (已禁用 - 误判率太高) ---
    # 模板匹配方案无法可靠检测地图，暂时禁用
    # 如需启用，请使用 Vision API 方案
    # try:
    #     image = Image.open(io.BytesIO(content))
    #     map_result = check_taiwan_region(image)
    #     ...
    # except Exception as e:
    #     print(f"⚠️ [地图检测] 跳过: {e}", flush=True)
    # --- 1. NudeNet 检测 (逻辑不变) ---
    try:
        temp_path = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            # [FIX] 使用 Pillow 统一转换为 JPG，防止 OpenCV 读取 WebP/AVIF 失败导致 NoneType 错误
            try:
                img_pil = Image.open(io.BytesIO(content))
                if img_pil.mode != "RGB":
                    img_pil = img_pil.convert("RGB")
                img_pil.save(tmp, format="JPEG")
            except Exception:
                # 如果转换失败（极少情况），尝试直接写入原数据
                tmp.write(content)
            temp_path = tmp.name
        
        detector = get_nude_detector()
        detections = detector.detect(temp_path)
        
        unsafe_items = []
        max_score = 0.0
        
        print("🧠 [NudeNet] 详细检测结果:", flush=True)
        if not detections:
            print("   (未检测到任何人体/器官特征)", flush=True)
        else:
            for item in detections:
                print(f"   {item['class']}: {item['score']:.4f}", flush=True)
            
        for item in detections:
            if item["class"] in UNSAFE_NUDENET_LABELS and item["score"] > 0.60: # 保持 0.60
                unsafe_items.append(f"{item['class']}({round(item['score'],2)})")
                max_score = max(max_score, item["score"])
        
        if unsafe_items:
            print(f"🚫 [NudeNet] 拦截: {', '.join(unsafe_items)}")
            if os.path.exists(temp_path): os.remove(temp_path)
            return {
                "safe": False,
                "score": max_score,
                "reason": f"包含裸露内容: {', '.join(unsafe_items)}",
                "details": {"nudenet": detections}
            }
        else:
            print("✅ [NudeNet] 通过")
            
    except Exception as e:
        error_msg = f"NudeNet Error: {str(e)}"
        print(f"❌ [NudeNet] 错误: {e}")
        result["details"]["nudenet_error"] = error_msg
    finally:
        if temp_path and os.path.exists(temp_path): os.remove(temp_path)

    # --- 2. Chinese-CLIP 检测 (中国政治内容) ---
    # [Lazy Import] 移除全局 HAS_CLIP 检查
    try:
        model, processor = get_chinese_clip()
        if model and processor:
                image = Image.open(io.BytesIO(content))
                inputs = processor(text=CHINESE_ALL_LABELS, images=image, return_tensors="pt", padding=True)
                
                with torch.no_grad():
                    outputs = model(**inputs)
                
                probs = outputs.logits_per_image.softmax(dim=1)
                probs_list = probs[0].tolist()
                
                sorted_probs = sorted(zip(CHINESE_ALL_LABELS, probs_list), key=lambda x: x[1], reverse=True)
                print("-" * 30)
                print("🧠 [Chinese-CLIP] 中国政治内容检测:")
                for l, p in sorted_probs[:3]:
                    print(f"   {l:<20}: {p:.4f}")
                
                max_prob = sorted_probs[0][1]
                max_label = sorted_probs[0][0]
                
                # [Fix] 分类别阈值：地图检测更敏感，旗帜检测更严格
                THRESHOLDS = {
                    "一张缺少台湾的错误中国地图": 0.40,  # 地图检测需要更敏感
                    "台独港独藏独旗帜": 0.60,            # 旗帜检测保持严格
                }
                
                if max_label in CHINESE_UNSAFE_LABELS:
                    threshold = THRESHOLDS.get(max_label, 0.50)  # 默认0.50
                    if max_prob > threshold:
                        print(f"🚫 [Chinese-CLIP] 政治问题! 命中: {max_label} (Score: {max_prob:.2f}, 阈值: {threshold})", flush=True)
                        return {
                            "safe": False,
                            "score": max_prob,
                            "reason": f"政治敏感: {max_label}",
                            "details": {"chinese_clip": dict(zip(CHINESE_ALL_LABELS, probs_list))}
                        }
                    else:
                        print(f"📊 [Chinese-CLIP] 未达阈值 (TOP: {max_label}, Score: {max_prob:.2f} < {threshold})", flush=True)
                else:
                    print(f"📊 [Chinese-CLIP] 通过 (TOP: {max_label})", flush=True)
                result["details"]["chinese_clip"] = dict(zip(CHINESE_ALL_LABELS, probs_list))
                    
    except Exception as e:
        error_msg = f"Chinese-CLIP Error: {str(e)}"
        print(f"❌ [Chinese-CLIP] 错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        result["details"]["chinese_clip_error"] = error_msg

    # --- 3. OpenAI CLIP 检测 (通用内容: 恐怖/暴力/毒品) ---
    # [Lazy Import] 移除全局 HAS_CLIP 检查
    try:
        model, processor = get_openai_clip()
        if model and processor:
                image = Image.open(io.BytesIO(content))
                inputs = processor(text=OPENAI_ALL_LABELS, images=image, return_tensors="pt", padding=True)
                
                with torch.no_grad():
                    outputs = model(**inputs)
                
                probs = outputs.logits_per_image.softmax(dim=1)
                probs_list = probs[0].tolist()
                
                sorted_probs = sorted(zip(OPENAI_ALL_LABELS, probs_list), key=lambda x: x[1], reverse=True)
                print("-" * 30)
                print("🧠 [OpenAI-CLIP] 通用内容检测:")
                for l, p in sorted_probs[:3]:
                    print(f"   {l:<40}: {p:.4f}")
                
                max_prob = sorted_probs[0][1]
                max_label = sorted_probs[0][0]
                
                GENERAL_THRESHOLD = 0.50
                if max_label in OPENAI_UNSAFE_LABELS and max_prob > GENERAL_THRESHOLD:
                    print(f"🚫 [OpenAI-CLIP] 危险内容! 命中: {max_label} (Score: {max_prob:.2f})", flush=True)
                    return {
                        "safe": False,
                        "score": max_prob,
                        "reason": f"危险内容: {max_label}",
                        "details": {"openai_clip": dict(zip(OPENAI_ALL_LABELS, probs_list))}
                    }
                else:
                    print(f"📊 [OpenAI-CLIP] 通过 (TOP: {max_label})", flush=True)
                    result["details"]["openai_clip"] = dict(zip(OPENAI_ALL_LABELS, probs_list))
                    
    except Exception as e:
        error_msg = f"OpenAI-CLIP Error: {str(e)}"
        print(f"❌ [OpenAI-CLIP] 错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        result["details"]["openai_clip_error"] = error_msg

    return result
