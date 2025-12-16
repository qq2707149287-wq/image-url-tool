"""
简化版功能验证脚本 - 跳过需要 auth 的测试
"""

import sys
import os
sys.path.append(os.getcwd())

from backend.database import init_db, get_db_connection, create_abuse_report, get_abuse_reports, create_notification, get_notifications
from backend.main import app
from fastapi.testclient import TestClient

# 初始化
client = TestClient(app)
init_db()

def test_1_report_api():
    """测试举报 API (匿名)"""
    report_data = {
        "image_hash": "test_verify_hash",
        "image_url": "http://localhost:8000/view/test_verify_hash",
        "reason": "Verification Test Report",
        "contact": "verify@example.com"
    }
    resp = client.post("/api/report", json=report_data)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    assert resp.json()["success"] is True
    print("✅ 1. 举报 API 测试通过")

def test_2_database_abuse_reports():
    """测试举报数据库操作"""
    # 创建举报
    result = create_abuse_report(
        image_hash="db_test_hash",
        image_url="http://localhost/test",
        reason="DB Test Report"
    )
    assert result["success"], f"Create report failed: {result}"
    
    # 获取举报
    reports = get_abuse_reports(status="pending")
    assert reports["success"], f"Get reports failed: {reports}"
    assert len(reports["data"]) > 0, "No reports found"
    
    # 检查刚创建的举报
    found = any(r["image_hash"] == "db_test_hash" for r in reports["data"])
    assert found, "Created report not found"
    print("✅ 2. 举报数据库操作测试通过")

def test_3_database_notifications():
    """测试通知数据库操作"""
    # 创建通知
    success = create_notification(
        device_id="test_device_123",
        type="system",
        title="Test Notification",
        message="This is a test notification"
    )
    assert success, "Create notification failed"
    
    # 获取通知
    notifs = get_notifications(device_id="test_device_123")
    assert len(notifs) > 0, "No notifications found"
    assert notifs[0]["title"] == "Test Notification"
    print("✅ 3. 通知数据库操作测试通过")

def test_4_notifications_api():
    """测试通知 API (匿名,应返回空列表而非错误)"""
    resp = client.get("/api/notifications")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    assert "notifications" in resp.json()
    print("✅ 4. 通知 API 测试通过")

def test_5_admin_page():
    """测试管理员页面可访问"""
    resp = client.get("/admin")
    assert resp.status_code == 200, f"Admin page failed: {resp.status_code}"
    assert "管理后台" in resp.text or "admin" in resp.text.lower()
    print("✅ 5. 管理员页面可访问测试通过")

if __name__ == "__main__":
    print("=" * 50)
    print("开始功能验证测试...")
    print("=" * 50)
    
    try:
        test_1_report_api()
        test_2_database_abuse_reports()
        test_3_database_notifications()
        test_4_notifications_api()
        test_5_admin_page()
        
        print("=" * 50)
        print("🎉 所有测试通过!")
        print("=" * 50)
    except AssertionError as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
