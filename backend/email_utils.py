# -*- coding: utf-8 -*-
# 邮件发送工具
# 使用标准 smtplib，支持 SSL (465) 和 STARTTLS (587) 两种模式

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
from dotenv import load_dotenv

load_dotenv()

# 从环境变量读取配置
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_PORT = int(os.getenv("MAIL_PORT", 465))
MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "私有云图床")

def send_email_sync(subject: str, email_to: str, html_body: str):
    """
    同步发送邮件（使用 smtplib）
    自动根据端口选择 SSL 或 STARTTLS 模式
    """
    # 创建邮件
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, 'utf-8')
    msg["From"] = formataddr((str(Header(MAIL_FROM_NAME, 'utf-8')), MAIL_FROM))
    msg["To"] = email_to
    
    # 添加 HTML 内容
    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)
    
    context = ssl.create_default_context()
    
    if MAIL_PORT == 465:
        # SSL 模式 (端口 465)
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, context=context, timeout=30) as server:
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, [email_to], msg.as_string())
    else:
        # STARTTLS 模式 (端口 587 或其他)
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=30) as server:
            server.starttls(context=context)
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, [email_to], msg.as_string())

async def send_verification_code(email: str, code: str):
    """发送注册验证码"""
    html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #4a90e2;">验证您的邮箱</h2>
        <p>您好！</p>
        <p>您正在注册私有云图床，您的验证码是：</p>
        <h1 style="background: #f0f0f0; padding: 10px 20px; display: inline-block; letter-spacing: 5px; color: #333;">{code}</h1>
        <p>验证码有效期为 10 分钟。</p>
        <p style="color: #999; font-size: 12px;">如果这不是您本人的操作，请忽略此邮件。</p>
    </div>
    """
    send_email_sync("【私有云图床】注册验证码", email, html)

async def send_password_reset_code(email: str, code: str):
    """发送重置密码验证码"""
    html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #e24a4a;">重置密码</h2>
        <p>您好！</p>
        <p>您正在申请重置密码，您的验证码是：</p>
        <h1 style="background: #f0f0f0; padding: 10px 20px; display: inline-block; letter-spacing: 5px; color: #333;">{code}</h1>
        <p>验证码有效期为 10 分钟。</p>
        <p style="color: #999; font-size: 12px;">如果这不是您本人的操作，请忽略此邮件。</p>
    </div>
    """
    send_email_sync("【私有云图床】重置密码验证码", email, html)
