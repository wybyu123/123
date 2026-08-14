import os
import json
from playwright.sync_api import sync_playwright

# ---------------- 配置区域 ----------------
# 直接请求 FOFA 的底层搜索接口（携带相同的 base64 查询条件）
TARGET_API_URL = "https://fofa.info/api/v1/search/all?qbase64=bmV3bGl2ZSAvbGl2ZQ==&size=100"
CSV_FILE = "202608100451.csv"
# ------------------------------------------

def get_existing_hosts(csv_path):
    """读取本地已有的 host 用于去重"""
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
    cookie_str = os.environ.get("FOFA_COOKIE")
    if not cookie_str:
        print("❌ 错误: 未检测到 FOFA_COOKIE 环境变量，请在 GitHub Secrets 中配置！")
        return

    print("🌐 正在通过浏览器会话请求 FOFA 内部接口...")
    new_items = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # 注入 Cookie
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
            # 先访问一次主页建立合法的 session 状态
            page.goto("https://fofa.info", timeout=30000)
            
            # 直接通过已登录的浏览器上下文请求底层数据接口
            print(f"📡 正在请求接口获取数据...")
            response = page.request.get(TARGET_API_URL)
            
            if response.status != 200:
                print(f"❌ 接口请求失败，状态码: {response.status}")
                return
                
            res_json = response.json()
            if res_json.get("error"):
                print(f"❌ FOFA 接口返回错误: {res_json.get('errmsg')}")
                return
                
            results = res_json.get("results", [])
            print(f"📊 成功获取到数据条数: {len(results)}")
            
            # FOFA search/all 接口返回的 fields 默认顺序一般是 [ip, port] 或类似结构
            for item in results:
                if len(item) >= 2:
                    ip = str(item[0]).strip()
                    port = str(item[1]).strip()
                    if ip and port.isdigit():
                        new_items.append((ip, port))
                                
        except Exception as e:
            print(f"❌ 请求过程发生异常: {e}")
        finally:
            browser.close()

    if not new_items:
        print("⚠️ 未能提取到有效的 IP 数据。")
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
        print("✨ 抓取到的 IP 在本地 CSV 中全部已存在。")
        return

    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("host,ip,port\n")
        f.writelines(new_rows)

    print(f"🚀 成功获取并向 {CSV_FILE} 补充了 {added_count} 条新记录！")

if __name__ == "__main__":
    fetch_fofa_web()
