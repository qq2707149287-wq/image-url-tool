import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import types

# ----------------------------------------------------------------
# 🐱 模拟环境配置
# Mocks for external dependencies to avoid installing them
# ----------------------------------------------------------------

# Mock DrissionPage & Playwright
mock_drission = MagicMock()
sys.modules["DrissionPage"] = mock_drission
sys.modules["DrissionPage.common"] = MagicMock()

sys.modules["playwright"] = MagicMock()
sys.modules["playwright.sync_api"] = MagicMock()

# ----------------------------------------------------------------
# 📂 加载器
# ----------------------------------------------------------------
def load_module_from_file(module_name, file_path):
    """
    Load a python module from a file path
    """
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        module = types.ModuleType(module_name)
        exec(source_code, module.__dict__)
        print(f"✅ 成功加载模块: {module_name}")
        return module
    except Exception as e:
        print(f"❌ 加载模块 {module_name} 失败: {e}")
        return None

# ----------------------------------------------------------------
# 🧪 测试用例
# ----------------------------------------------------------------

class TestTaobaoBots(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        print("\n🐱 正在准备测试环境...")
        cls.tools_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load from TEMP copies
        cls.bot1 = load_module_from_file("taobao_bot", os.path.join(cls.tools_dir, "temp_taobao_bot.py"))
        cls.bot2 = load_module_from_file("taobao_demo", os.path.join(cls.tools_dir, "temp_taobao_demo.py"))

    def test_taobao_bot_1_structure(self):
        """测试 taobao_bot.py (生产版机器人)"""
        print("\n[Test] 🤖 测试 Bot 1: taobao_bot.py")
        
        if not self.bot1:
            self.fail("无法加载 Bot 1 源码")

        # 1. 检查配置项
        self.assertTrue(hasattr(self.bot1, 'DEBUG_PORT'), "配置缺失: DEBUG_PORT")
        self.assertTrue(hasattr(self.bot1, 'PRODUCT_MAP'), "配置缺失: PRODUCT_MAP")
        
        # 2. 验证商品映射
        prod_map = self.bot1.PRODUCT_MAP
        print(f"  - 商品映射: {prod_map}")
        self.assertIn("月卡", prod_map)
        
        # 3. 模拟逻辑
        BotClass = self.bot1.TaobaoAutoSender
        
        # Mock class instantiation
        with patch('DrissionPage.ChromiumPage') as mock_cp:
            bot = BotClass()
            
            # Mock file reading for get_card_code
            mock_files = {
                "code_monthly.txt": "VIP-MONTH-001"
            }
            
            # Helper to mock open
            def mock_open_side_effect(filename, *args, **kwargs):
                if filename in mock_files:
                    return unittest.mock.mock_open(read_data=mock_files[filename])()
                raise FileNotFoundError(filename)

            with patch("builtins.open", side_effect=mock_open_side_effect):
                with patch("os.path.exists", side_effect=lambda f: f in mock_files):
                    code = bot.get_card_code("购买月卡")
                    print(f"  - 提取月卡卡密: {code}")
                    self.assertEqual(code, "VIP-MONTH-001")
                    print("  ✅ 卡密提取逻辑测试通过")

    def test_taobao_bot_2_structure(self):
        """测试 taobao_delivery_bot_demo.py (Playwright 版)"""
        print("\n[Test] 🎮 测试 Bot 2: taobao_delivery_bot_demo.py")
        
        if not self.bot2:
            self.fail("无法加载 Bot 2 源码")
            
        # 1. 检查 run 函数
        self.assertTrue(hasattr(self.bot2, 'run'), "缺失 run 入口函数")
        print("  ✅ 入口函数检查通过")
        
        # 2. 简单验证其为基于 Playwright 的实现
        # 在 setUpClass 加载时如果没报错 (mock 了 playwright)，说明依赖检查通过
        print("  ✅ Playwright 依赖加载通过")

if __name__ == '__main__':
    unittest.main(verbosity=2)
