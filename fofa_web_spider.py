import os
from playwright.sync_api import sync_playwright

# ---------------- 配置区域 ----------------
TARGET_URL = "https://fofa.info/result?qbase64=bmV3bGl2ZSAvbGl2ZQ=="
CSV_FILE = "202608100451.csv"
# ------------------------------------------

def get_existing_hosts(csv_path):
    existing = set()
    if not os.path.exists(csv_path):
        return existing
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[1:]:
            parts = line.strip().split(",")
            if parts and parts[0]:
                existing.add(parts[0].strip())
    return existing

def fetch_fofa_web():
    # 从 GitHub Secrets 获取 Cookie
    cookie_str = os.environ.get("FOFA_COOKIE")
    if not cookie_str:
        print("❌ 错误: 未检测到 FOFA_COOKIE 环境变量，请在 GitHub Secrets 中配置！")
        return

    print(f"🌐 正在启动带 Cookie 的浏览器访问 FOFA: {TARGET_URL}")
    new_items = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # 将你的 Cookie 字符串解析并注入到浏览器上下文中
        cookies = []
        for item in cookie_str.split(";"):
            if "=" in item:
                try:
                    name, val = item.strip().split("=", 1)
                    cookies.append({
                        "name": name, 
                        "value": val, 
                        "domain": ".fofa.info", 
                        "path": "/"
                    })
                except Exception:
                    continue
        if cookies:
            context.add_cookies(cookies)
            print("🍪 成功注入用户登录 Cookie")

        page = context.new_page()
        
        try:
            page.goto(TARGET_URL, timeout=60000)
            print("⏳ 正在等待网页渲染数据表格...")
            # 等待表格加载
            page.wait_for_selector(".el-table__body", timeout=25000)
            
            rows = page.locator(".el-table__body tr")
            count = rows.count()
            print(f"📊 浏览器成功抓取到表格行数: {count}")
            
            for i in range(count):
                row_text = rows.nth(i).inner_text()
                lines = row_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if ":" in line and "." in line:
                        parts = line.split(":")
                        if len(parts) >= 2 and parts[0].replace(".", "").isdigit():
                            ip = parts[0].strip()
                            port = parts[1].split()[0].strip()
                            if ip and port.isdigit():
                                new_items.append((ip, port))
                                
        except Exception as e:
            print(f"❌ 抓取过程发生异常（可能是 Cookie 过期或仍被拦截）: {e}")
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
        def add_host():
            existing_hosts.add(host)
            new_rows.append(f"{host},{ip},{port}\n")
            nonlocal added_count
            added_count += 1
        add_host()

    if added_count == 0:
        print("✨ 抓取到的 IP 在本地 CSV 中全部已存在。")
        return

    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("host,ip,port\n")
        f.writelines(new_rows)

    print(f"🚀 成功从 FOFA 网页抓取并补充了 {added_count} 条新记录到 {CSV_FILE}")

if __name__ == "__main__":
    fetch_fofa_web()
