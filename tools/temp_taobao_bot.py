# -*- coding: utf-8 -*-
import time
import random
import os
from DrissionPage import ChromiumPage, ChromiumOptions

# ================= 配置区域 =================
# 调试端口（需与启动浏览器的参数一致）
DEBUG_PORT = 9222

# 商品关键词与卡密文件映射
# 格式：{"关键词": "卡密文件名.txt"}
PRODUCT_MAP = {
    "月卡": "code_monthly.txt",
    "年卡": "code_yearly.txt",
    "VIP会员": "code_vip.txt"
}

# 自动回复话术模板
MSG_TEMPLATE = "亲，您购买的{item_name}激活码如下：\n{code}\n请访问 [我的网站地址] 进行激活。感谢支持！"

# 已处理订单记录（防止脚本重启后重复发货，实际生产建议存数据库或文件）
PROCESSED_ORDERS = set()
# ===========================================

class TaobaoAutoSender:
    def __init__(self):
        # 连接已打开的浏览器
        co = ChromiumOptions().set_local_port(DEBUG_PORT)
        self.page = ChromiumPage(addr_or_opts=co)
        print("✅ 成功连接到浏览器，开始接管...")

    def log(self, msg):
        """简单的日志输出"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{timestamp}] {msg}")

    def random_sleep(self, min_s=2, max_s=5):
        """随机延时，模拟人类"""
        t = random.uniform(min_s, max_s)
        time.sleep(t)

    def get_card_code(self, keyword):
        """
        根据关键词读取并移除卡密
        """
        filename = None
        # 简单的模糊匹配关键词
        for key, fname in PRODUCT_MAP.items():
            if key in keyword:
                filename = fname
                break
        
        if not filename or not os.path.exists(filename):
            self.log(f"❌ 错误：未找到商品 [{keyword}] 对应的卡密文件或文件不存在。")
            return None

        # 读取并删除第一行
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                self.log(f"❌ 警告：文件 {filename} 已空，无库存！")
                return None
            
            code = lines[0].strip()
            
            # 写回剩余行
            with open(filename, 'w', encoding='utf-8') as f:
                f.writelines(lines[1:])
            
            return code
        except Exception as e:
            self.log(f"❌ 读取卡密文件出错: {e}")
            return None

    def send_wangwang_msg(self, buyer_nick, message):
        """
        发送旺旺消息
        注意：这通常会打开一个新的千牛聊天窗口或弹窗
        """
        self.log(f"正在给买家 [{buyer_nick}] 发送消息...")
        
        # 这里模拟点击页面上的“联系买家”图标，通常在订单列表里有一个旺旺图标
        # 或者直接访问阿里旺旺的Web协议链接（更稳定）
        # 示例：尝试查找当前订单行内的旺旺图标并点击 (需要根据实际DOM调整)
        # 为简化，这里演示直接通过千牛Web版URL机制（假设已登录）
        
        try:
            # 打开新标签页访问千牛聊天页面 (这是一个通用的Web聊天跳转链接)
            # 实际千牛网页版URL可能很复杂，这里建议尽量复用页面上的点击操作
            # 下面演示点击操作逻辑：
            
            # 假设我们还在订单列表页，通常不需要专门点击发消息，
            # 可以在发货时的备注里写，或者发货后点击列表里的旺旺。
            # 这里为了演示，我们假设不通过点击，而是打印出来模拟发送成功
            # 因为千牛Web版聊天窗口通常是 iframe 或 独立窗口，控制较复杂。
            
            # 真实场景建议：直接在发货备注里填写卡密，或者点击“联系买家”
            # self.page.ele(f'@title:联系买家', index=1).click() 
            # new_tab = self.page.get_tab(title='千牛聊天')
            # new_tab.ele('textarea').input(message)
            # new_tab.ele('text:发送').click()
            # new_tab.close()
            
            self.log(f"模拟发送旺旺消息成功：\n{message}")
            return True
        except Exception as e:
            self.log(f"⚠️ 发送消息失败: {e}")
            return False

    def ship_item(self, order_ele, order_id):
        """
        执行发货操作：点击发货 -> 选择无需物流 -> 确认
        """
        try:
            # 1. 点击“发货”按钮
            # 淘宝的按钮文字通常是 "发货"
            btn_ship = order_ele.ele('text:发货', timeout=2)
            if not btn_ship:
                self.log(f"订单 {order_id} 未找到发货按钮，可能状态已变。")
                return False
            
            btn_ship.click()
            self.random_sleep(1, 2)

            # 等待发货弹窗/页面加载
            # 注意：淘宝发货可能是在当前页弹窗，也可能是跳转新页面
            # DrissionPage 会自动处理当前页面变化，如果是新标签页需要切换
            
            # 2. 选择“无需物流” (虚拟商品)
            # 这里需要根据实际弹窗的DOM结构来定，通常有一个 Tab 叫 "无需物流"
            # 或者单选框 "虚拟物品"
            no_logistics_tab = self.page.ele('text:无需物流', timeout=5)
            if no_logistics_tab:
                no_logistics_tab.click()
                self.random_sleep(0.5, 1)
            else:
                self.log(f"⚠️ 未找到'无需物流'选项，尝试直接查找'确认'...")

            # 3. 点击“确认”或“发货”
            confirm_btn = self.page.ele('text:确认', timeout=2) or self.page.ele('css:button.primary', timeout=2)
            if confirm_btn:
                # 危险操作，实际测试时建议注释掉下面这一行
                confirm_btn.click() 
                self.log(f"✅ 订单 {order_id} 已执行发货点击。")
                return True
            else:
                self.log(f"❌ 订单 {order_id} 找不到确认按钮。")
                return False

        except Exception as e:
            self.log(f"❌ 发货流程出错: {e}")
            return False

    def monitor_loop(self):
        """主循环"""
        self.log("🚀 监控脚本已启动，按下 Ctrl+C 停止...")
        
        while True:
            try:
                # 1. 确保在“已卖出的宝贝”页面
                if "已卖出的宝贝" not in self.page.title:
                    self.log("正在跳转至订单列表页...")
                    # 这里填入淘宝卖家中心已卖出宝贝的链接
                    self.page.get('https://myseller.taobao.com/home.htm/trade-platform/tp/sold') 
                    self.random_sleep(3, 5)

                # 2. 刷新页面以获取最新订单
                self.page.refresh()
                self.log("页面已刷新，检查新订单...")
                
                # 等待订单列表加载 (根据实际的class修改，这里用text定位比较通用)
                self.page.wait.ele_display('text:订单号', timeout=10)

                # 3. 获取所有订单行
                # 淘宝订单结构通常是一层层的 div
                # 我们先找包含 "买家已付款" 状态的容器
                # 这里的 xpath 只是示例，淘宝前端代码混淆严重，建议使用 text 相对定位
                
                # 策略：找到所有包含 "等待卖家发货" 或 "买家已付款" 的元素
                # 然后向上查找父级获取整个订单块
                status_eles = self.page.eles('text:买家已付款')
                
                for status_ele in status_eles:
                    # 获取订单容器 (假设向上找3-4层是订单行，需F12调试确定)
                    order_row = status_ele.parent(4) 
                    
                    # 提取订单号
                    # 假设订单号在某个 span 里
                    order_id_ele = order_row.ele('text:订单号', timeout=1)
                    if order_id_ele:
                        # 简单的文本处理提取数字
                        order_id_text = order_id_ele.parent().text
                        order_id = ''.join(filter(str.isdigit, order_id_text))
                    else:
                        continue

                    if order_id in PROCESSED_ORDERS:
                        continue

                    # 提取商品名称
                    # 通常是 class 为 item-title 或者包含 href 的链接
                    title_ele = order_row.ele('tag:a', index=2) # 索引需要调试
                    item_name = title_ele.text if title_ele else "未知商品"

                    # 提取买家昵称
                    buyer_ele = order_row.ele('css:.buyer-mod__name', timeout=1) # 示例class
                    buyer_nick = buyer_ele.text if buyer_ele else "未知买家"

                    self.log(f"🔎 发现待发货订单: {order_id} | 商品: {item_name}")

                    # 4. 获取卡密
                    code = self.get_card_code(item_name)
                    if not code:
                        self.log("⚠️ 无可用卡密，跳过此订单。")
                        continue

                    # 5. 执行发货流程
                    # 组装消息
                    full_msg = MSG_TEMPLATE.format(item_name=item_name, code=code)
                    
                    # 发送消息 (可选：如果只想发货在备注里，可以修改逻辑)
                    self.send_wangwang_msg(buyer_nick, full_msg)
                    self.random_sleep(2, 4)

                    # 点击发货
                    if self.ship_item(order_row, order_id):
                        self.log(f"✅ 订单 {order_id} 处理完毕！")
                        PROCESSED_ORDERS.add(order_id)
                    
                    self.random_sleep(3, 6)

            except Exception as e:
                self.log(f"⚠️ 循环发生异常: {e}")
                # 防止死循环报错，等待长一点时间
                time.sleep(10)

            # 循环间隔
            wait_time = random.randint(15, 30)
            self.log(f"等待 {wait_time} 秒后进行下一次检查...")
            time.sleep(wait_time)

if __name__ == "__main__":
    bot = TaobaoAutoSender()
    bot.monitor_loop()