# 简化的 SMTP 诊断脚本
import smtplib
import ssl

MAIL_SERVER = "smtp.qq.com"
MAIL_USERNAME = "2807149287@qq.com"
MAIL_PASSWORD = "kizocnhsbcfwddjc"

print("测试 587 端口 (STARTTLS)...")
try:
    with smtplib.SMTP(MAIL_SERVER, 587, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("587 端口: 成功")
except Exception as e:
    print(f"587 端口: 失败 - {type(e).__name__}: {e}")

print("\n测试 465 端口 (SSL)...")
try:
    with smtplib.SMTP_SSL(MAIL_SERVER, 465, context=ssl.create_default_context(), timeout=15) as server:
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("465 端口: 成功")
except Exception as e:
    print(f"465 端口: 失败 - {type(e).__name__}: {e}")
