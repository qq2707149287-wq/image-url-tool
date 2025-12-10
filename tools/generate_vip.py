import sys
import os
# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database
import uuid

def main():
    print("💎 VIP 激活码生成工具")
    print("-" * 30)
    
    # Initialize DB (just in case, though usually main.py does it)
    # database.init_db() # database.py's init_db is safe to call multiple times?
    # Checking database.py: 
    # def init_db(): ... create tables if not exists ...
    # Yes.
    database.init_db()

    try:
        days = input("请输入 VIP 有效天数 (默认 30): ").strip()
        if not days:
            days = 30
        else:
            days = int(days)
            
        count = input("请输入生成数量 (默认 1): ").strip()
        if not count:
            count = 1
        else:
            count = int(count)
            
        print(f"\n正在生成 {count} 个 {days} 天的激活码...\n")
        
        for i in range(count):
            # Generate code like XXXX-XXXX-XXXX-XXXX
            raw_code = uuid.uuid4().hex[:16].upper()
            formatted_code = f"{raw_code[:4]}-{raw_code[4:8]}-{raw_code[8:12]}-{raw_code[12:]}"
            
            if database.create_vip_code(formatted_code, days):
                print(f"[{i+1}] {formatted_code}")
                
        print("\n✅ 生成完成！")
        
    except ValueError:
        print("\n❌ 错误: 请输入有效的数字")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")

if __name__ == "__main__":
    main()
