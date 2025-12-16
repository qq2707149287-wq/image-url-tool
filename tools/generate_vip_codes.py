import sys
import os
import secrets
import string
import argparse

# 添加项目根目录到 path 以便导入 backend 模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import create_vip_code, init_db

def generate_code(length=16):
    """生成易读的激活码 (大写字母+数字)"""
    chars = string.ascii_uppercase + string.digits
    # 格式: XXXX-XXXX-XXXX-XXXX
    raw = ''.join(secrets.choice(chars) for _ in range(length))
    return '-'.join(raw[i:i+4] for i in range(0, length, 4))

def main():
    parser = argparse.ArgumentParser(description="批量生成 VIP 激活码 (用于淘宝/发卡网)")
    parser.add_argument("-n", "--number", type=int, default=10, help="生成数量 (默认为 10)")
    parser.add_argument("-d", "--days", type=int, default=30, help="VIP 有效天数 (默认为 30)")
    parser.add_argument("-o", "--output", type=str, default="vip_codes.txt", help="输出文件路径")
    
    args = parser.parse_args()
    
    print(f"🔄 正在生成 {args.number} 个激活码 (天数: {args.days})...")
    
    # 确保数据库已连接
    init_db()
    
    success_count = 0
    codes = []
    
    for _ in range(args.number):
        code = generate_code()
        if create_vip_code(code, args.days):
            codes.append(code)
            success_count += 1
            print(f"  ✅ {code}")
        else:
            print(f"  ❌ 生成失败 (可能重复)")
            
    # 写入文件
    with open(args.output, "a", encoding="utf-8") as f:
        f.write(f"\n# Batch Generated at {os.times}\n")
        f.write(f"# Days: {args.days}\n")
        for c in codes:
            f.write(f"{c}\n")
            
    print(f"\n🎉 完成! 成功生成 {success_count} 个激活码。")
    print(f"📂 已保存至: {os.path.abspath(args.output)}")
    print("您可以直接将此文件内容复制到淘宝自动发货软件或发卡平台中。")

if __name__ == "__main__":
    main()
