import smtplib
import imaplib
import email
import time
import os
import random
from email.mime.text import MIMEText
from email.header import decode_header

# 配置信息 (请修改为您的邮箱)
EMAIL_USER = "your_email@example.com"
EMAIL_PASS = "your_app_password"  # Google/QQ 邮箱请使用应用专用密码
IMAP_SERVER = "imap.example.com"
SMTP_SERVER = "smtp.example.com"
TRIGGER_SUBJECT = "购买VIP" # 邮件标题包含此词触发
CODE_FILE = "vip_codes.txt" # 激活码库存文件

def get_code_from_file():
    """从文件中取出一个激活码，并将其移除"""
    if not os.path.exists(CODE_FILE):
        return None
    
    with open(CODE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 过滤掉注释和空行
    valid_lines = [l for l in lines if l.strip() and not l.startswith("#")]
    
    if not valid_lines:
        return None
        
    code_to_send = valid_lines[0].strip()
    
    # 写回文件 (移除已发送的)
    # 注意：这里简单粗暴地移除第一行有效数据。为了保留注释，我们需要保留 header
    new_content = []
    removed = False
    for line in lines:
        if not removed and line.strip() == code_to_send:
            removed = True
            continue # 跳过这一行 (相当于删除)
        new_content.append(line)
        
    with open(CODE_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_content)
        
    return code_to_send

def send_reply(to_addr, code):
    """发送回信"""
    msg = MIMEText(f"亲爱的用户，\n\n感谢您的购买！\n\n您的 VIP 激活码是：\n{code}\n\n请在网页端【激活 VIP】处输入使用。\n有效期：30天\n\n祝您使用愉快！", 'plain', 'utf-8')
    msg['Subject'] = "【自动发货】您的 VIP 激活码"
    msg['From'] = EMAIL_USER
    msg['To'] = to_addr

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"✅ 已发送激活码 {code} 给 {to_addr}")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False

def check_email():
    """检查未读邮件"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # 搜索所有未读邮件
        status, messages = mail.search(None, 'UNSEEN')
        
        email_ids = messages[0].split()
        if not email_ids:
            return

        print(f"📧 发现 {len(email_ids)} 封未读邮件...")

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            
            # 解析标题
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")
            
            # 解析发件人
            from_addr = email.utils.parseaddr(msg.get("From"))[1]
            
            print(f"  📩 [{subject}] 来自 {from_addr}")

            if TRIGGER_SUBJECT in subject:
                print("    ⚡ 触发自动发货规则！")
                code = get_code_from_file()
                
                if code:
                    if send_reply(from_addr, code):
                        # 标记为已读 (默认 fetch 后只要不改 flag 应该就是已读，或者需要显式设置)
                        # mail.store(e_id, '+FLAGS', '\\Seen') 
                        pass
                else:
                    print("    ⚠️ 库存不足！无法发送。")
                    # 可选择回复库存不足的通知
            
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"❌ 邮件检查出错: {e}")

def main():
    print("🤖 邮件自动发货机器人已启动...")
    print(f"📂 监听库存文件: {CODE_FILE}")
    print(f"📨 触发关键词: {TRIGGER_SUBJECT}")
    
    if not os.path.exists(CODE_FILE):
        print("⚠️ 警告: vip_codes.txt 不存在，请先使用 generate_vip_codes.py 生成！")

    while True:
        check_email()
        time.sleep(30) # 每 30 秒检查一次

if __name__ == "__main__":
    main()
