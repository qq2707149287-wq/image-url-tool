import sqlite3
import sys
import os

def make_admin():
    # 获取项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    db_path = os.path.join(project_root, "backend", "history.db")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"❌ 错误: 找不到数据库文件 {db_path}")
        print("请确保你在项目根目录下运行此脚本。")
        return

    print("="*40)
    print("      👑 管理员提升工具       ")
    print("="*40)

    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("请输入要设置为管理员的用户名: ").strip()
    
    if not username:
        print("❌ 用户名不能为空")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 1. 检查用户是否存在
        c.execute("SELECT id, is_admin FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        
        if not user:
            print(f"❌ 找不到用户: '{username}'")
            print("请先在网页上注册该用户。")
            return
            
        user_id, is_admin = user
        
        if is_admin:
            print(f"⚠️  用户 '{username}' 已经是管理员了。")
            return

        # 2. 更新为管理员
        c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
        conn.commit()
        
        if c.rowcount > 0:
            print(f"✅ 成功! 用户 [{username}] 已升级为管理员。")
            print("👉 请重新登录以使权限生效。")
        else:
            print("❌ 更新失败，未做任何更改。")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    make_admin()
