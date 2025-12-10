# 测试邮件发送 - 同时测试 465 和 587 端口
import smtplib
import ssl
from email.mime.text import MIMEText

MAIL_SERVER = "smtp.qq.com"
MAIL_USERNAME = "2807149287@qq.com"
MAIL_PASSWORD = "kizocnhsbcfwddjc"  # 授权码

print("=" * 50)
print("测试 QQ 邮箱 SMTP 连接")
print("=" * 50)

# 测试 1: 尝试 587 端口 + STARTTLS
print("\n[1] 尝试 587 端口 (STARTTLS)...")
try:
    context = ssl.create_default_context()
    with smtplib.SMTP(MAIL_SERVER, 587, timeout=15) as server:
        server.set_debuglevel(1)
        server.starttls(context=context)
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("✅ 587 端口连接成功!")
except Exception as e:
    print(f"❌ 587 端口失败: {e}")

# 测试 2: 尝试 465 端口 + SSL
print("\n[2] 尝试 465 端口 (SSL)...")
try:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(MAIL_SERVER, 465, context=context, timeout=15) as server:
        server.set_debuglevel(1)
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("✅ 465 端口连接成功!")
except Exception as e:
    print(f"❌ 465 端口失败: {e}")

print("\n测试完成。")
