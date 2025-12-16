import sys
import os
import secrets
import string

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import database
from backend.routers.auth import get_password_hash

def generate_password(length=12):
    """生成随机密码"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def main():
    print("=" * 40)
    print("   🔐 快速创建管理员账号工具")
    print("=" * 40)
    print("(跳过邮箱验证，直接入库)\n")
    
    # 初始化数据库
    database.init_db()
    
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("请输入用户名 (默认: admin): ").strip() or "admin"
    
    if len(sys.argv) > 2:
        password = sys.argv[2]
    else:
        default_pwd = generate_password()
        password = input(f"请输入密码 (直接回车使用随机密码 {default_pwd}): ").strip() or default_pwd
    
    # 检查用户名是否已存在
    if database.get_user_by_username(username):
        print(f"❌ 用户名 '{username}' 已存在！")
        print("如需将其设为管理员，请使用: python tools/make_admin.py " + username)
        return
    
    # 创建用户
    hashed_password = get_password_hash(password)
    
    # 使用邮箱注册方法 (email 可以留空或设为占位符)
    email = f"{username}@local.admin"
    success = database.create_email_user(username, email, hashed_password)
    
    if not success:
        print("❌ 创建用户失败！")
        return
    
    # 立即设为管理员
    try:
        with database.get_db_connection() as conn:
            conn.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
            conn.commit()
        
        print("\n" + "=" * 40)
        print("✅ 管理员账号创建成功！")
        print("=" * 40)
        print(f"   用户名: {username}")
        print(f"   密码:   {password}")
        print(f"   邮箱:   {email}")
        print("=" * 40)
        print("\n请记住上述信息，然后在网页登录。")
        
    except Exception as e:
        print(f"❌ 设置管理员权限失败: {e}")

if __name__ == "__main__":
    main()
