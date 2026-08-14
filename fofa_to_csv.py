import os
from playwright.sync_api import sync_playwright

# ---------------- 配置区域 ----------------
TARGET_URL = "https://fofa.info/result?qbase64=bmV3bGl2ZSAvbGl2ZQ=="
CSV_FILE = "202608100451.csv"
# ------------------------------------------

def get_existing_hosts(csv_path):
    """读取本地已有的 host 用于去重"""
    existing = set()
    if not os.path.exists(csv_path):
        return existing
    
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[1:]: # 跳过表头
            parts = line.strip().split(",")
            if parts and parts[0]:
                existing.add(parts[0].strip())
    return existing

def fetch_fofa_web():
    print(f"🌐 正在启动浏览器访问 FOFA 页面: {TARGET_URL}")
    
    new_items = []
    
    with sync_playwright() as p:
        # 启动无头浏览器
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()
        
        try:
            # 访问目标搜索链接
            page.goto(TARGET_URL, timeout=60000)
            
            # 等待页面上的数据表格加载出来
            print("⏳ 正在等待网页渲染数据...")
            page.wait_for_selector(".el-table__body", timeout=20000)
            
            # 抓取页面上所有的文本或者通过选择器精准提取 IP 和 端口
            # 这里我们获取页面上所有的链接或文本，通过正则或解析提取出 IP:Port
            content = page.content()
            
            # 利用 Playwright 获取表格里的每一行数据
            rows = page.locator(".el-table__body tr")
            count = rows.count()
            print(f"📊 浏览器成功抓取到网页表格行数: {count}")
            
            for i in range(count):
                row_text = rows.nth(i).inner_text()
                # 根据 FOFA 网页的文本结构，提取其中的 IP 和端口
                # 通常表格里会包含 IP 和端口信息，我们按行分割或正则提取
                lines = row_text.split("\n")
                for line in lines:
                    line = line.strip()
                    # 简单匹配 IP:Port 格式
                    if ":" in line and "." in line:
                        parts = line.split(":")
                        if len(parts) >= 2 and parts[0].replace(".", "").isdigit():
                            ip = parts[0].strip()
                            port = parts[1].split()[0].strip() # 防止后面有其他多余文字
                            if ip and port.isdigit():
                                new_items.append((ip, port))
                                
        except Exception as e:
            print(f"❌ 抓取过程发生异常（可能触发了安全拦截或需要登录）: {e}")
        finally:
            browser.close()

    if not new_items:
        print("⚠️ 未能从网页中提取到有效的 IP 数据。")
        return

    # 去重并写入 CSV
    existing_hosts = get_existing_hosts(CSV_FILE)
    new_rows = []
    added_count = 0

    for ip, port in new_items:
        host = f"{ip}:{port}"
        if host not in existing_hosts:
            existing_hosts.add(host)
            new_rows.append(f"{host},{ip},{port}\n")
            added_count += 1

    if added_count == 0:
        print("✨ 网页抓取到的 IP 在本地 CSV 中全部已存在，无需更新。")
        return

    # 追加写入文件
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("host,ip,port\n")
        f.writelines(new_rows)

    print(f"🚀 成功从 FOFA 网页抓取并补充了 {added_count} 条新记录到 {CSV_FILE}")

if __name__ == "__main__":
    fetch_fofa_web()
