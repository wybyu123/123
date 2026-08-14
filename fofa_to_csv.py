import base64
import os
import requests

# ---------------- 配置区域 ----------------
QUERY_STR = 'newlive /live'           # 搜索语句
CSV_FILE = "202608100451.csv"         # 你的本地 CSV 文件名
MAX_SIZE = 100                        # 每次抓取获取的最大条数
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

def fetch_and_append_fofa():
    # 从环境变量中安全获取 GitHub Secrets 注入的配置
    fofa_email = os.environ.get("FOFA_EMAIL")
    fofa_key = os.environ.get("FOFA_KEY")
    
    if not fofa_email or not fofa_key:
        print("❌ 错误: 未检测到 FOFA_EMAIL 或 FOFA_KEY 环境变量！")
        return

    print(f"📡 正在通过 FOFA API 查询: {QUERY_STR}")
    
    # 1. Base64 编码查询语句
    qbase64 = base64.b64encode(QUERY_STR.encode("utf-8")).decode("utf-8")
    
    # 2. 请求 FOFA API
    url = f"https://fofa.info/api/v1/search/all?email={fofa_email}&key={fofa_key}&qbase64={qbase64}&fields=ip,port&size={MAX_SIZE}"
    
    try:
        response = requests.get(url, timeout=15)
        res_json = response.json()
        
        if res_json.get("error"):
            print(f"❌ FOFA 接口报错: {res_json.get('errmsg')}")
            return
        
        results = res_json.get("results", [])
        print(f"📊 FOFA 本次成功返回: {len(results)} 条数据")
        
        if not results:
            return

        # 3. 加载本地已有数据进行去重
        existing_hosts = get_existing_hosts(CSV_FILE)
        
        new_rows = []
        added_count = 0
        
        for item in results:
            ip = item[0]
            port = str(item[1])
            host = f"{ip}:{port}"
            
            # 去重判断
            if host not in existing_hosts:
                existing_hosts.add(host)
                new_rows.append(f"{host},{ip},{port}\n")
                added_count += 1
                
        if added_count == 0:
            print("✨ 没有发现全新内容，本地 CSV 无需更新。")
            return

        # 4. 写入文件 (若文件不存在则自动创建并写入表头)
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write("host,ip,port\n")
            f.writelines(new_rows)
            
        print(f"🚀 成功增量补充！本次向 {CSV_FILE} 新增了 {added_count} 条记录。")

    except Exception as e:
        print(f"❌ 请求发生异常: {e}")

if __name__ == "__main__":
    fetch_and_append_fofa()
