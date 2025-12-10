import subprocess
import winsound
import sys
import os

def print_header(title):
    print("\n" + "=" * 40)
    print(f" {title}")
    print("=" * 40)

def check_service(service_name, display_name):
    print(f"\n[-] 正在检查服务: {display_name} ({service_name})...")
    try:
        # sc query service_name returns non-zero if service doesn't exist, but usually standard output needs parsing
        result = subprocess.run(["sc", "query", service_name], capture_output=True, text=True)
        if result.returncode == 0:
            if "RUNNING" in result.stdout:
                print(f"    [OK] 服务正在运行。")
            else:
                print(f"    [!] 服务未运行。状态可能为停止或暂停。")
                print(f"    调试信息:\n{result.stdout.strip()}")
        else:
            print(f"    [X] 无法查询服务状态。错误代码: {result.returncode}")
    except Exception as e:
        print(f"    [X] 检查出错: {e}")

def list_audio_devices():
    print_header("音频设备检测")
    print("\n[-] 正在获取音频设备列表 (WMI)...")
    try:
        # Use simple wmic command
        cmd = ["wmic", "sounddev", "get", "Caption,Status,Manufacturer"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # Filter out empty lines
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            for line in lines:
                print(f"    {line}")
        else:
            print("    [!] 无法获取设备列表。")
    except Exception as e:
        print(f"    [X] 获取设备出错: {e}")

def play_sound_test():
    print_header("音频播放测试")
    print("\n[-] 尝试播放系统提示音 (MessageBeep)...")
    try:
        winsound.MessageBeep(winsound.MB_OK)
        print("    [?] 你听到提示音了吗？")
    except Exception as e:
        print(f"    [X] 播放提示音失败: {e}")

    print("\n[-] 尝试播放蜂鸣声 (1000Hz, 500ms)...")
    try:
        winsound.Beep(1000, 500)
        print("    [?] 你听到蜂鸣声了吗？")
    except Exception as e:
        print(f"    [X] 播放蜂鸣声失败: {e}")

def main():
    print_header("Windows 音频问题诊断工具")
    print("本工具将检查音频服务状态、列出设备并尝试播放声音。")
    
    # Check Services
    print_header("服务状态检查")
    check_service("Audiosrv", "Windows Audio")
    check_service("AudioEndpointBuilder", "Windows Audio Endpoint Builder")
    
    # List Devices
    list_audio_devices()
    
    # Test Sound
    play_sound_test()
    
    print("\n" + "=" * 40)
    print("诊断完成。")
    print("如果服务未运行，请尝试在服务管理器中启动它们。")
    print("如果听不到声音但看来一切正常，请检查物理静音开关或扬声器连接。")
    print("=" * 40)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消操作。")
    except Exception as e:
        print(f"\n\n发生未预期的错误: {e}")
