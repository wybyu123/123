import os
import csv
import requests

# 创建下载文件夹
output_dir = "downloads"
os.makedirs(output_dir, exist_ok=True)

csv_file = "202608100451.csv"

if not os.path.exists(csv_file):
    print(f"找不到文件: {csv_file}")
    exit(1)

with open(csv_file, mode="r", encoding="utf-8") as f:
    reader = csv.reader(f)
    next(reader, None)  # 跳过表头 (host, ip, port)
    
    for index, row in enumerate(reader):
        if not row:
            continue
        host_val = row[0].strip()
        
        # 智能补全 URL 协议
        if host_val.startswith("http://") or host_val.startswith("https://"):
            url = host_val
        else:
            url = f"http://{host_val}"
            
        print(f"正在请求 [{index+1}]: {url}")
        
        try:
            # 模拟浏览器 User-Agent 访问，设置 10 秒超时
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # 给文件起个安全的名字（替换掉特殊字符）
                safe_name = host_val.replace("://", "_").replace("/", "_").replace(":", "_")
                file_path = os.path.join(output_dir, f"result_{index+1}_{safe_name}.txt")
                
                with open(file_path, "w", encoding="utf-8", errors="ignore") as out:
                    out.write(response.text)
                print(f"成功保存: {file_path}")
            else:
                print(f"请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            print(f"访问出错 {url}: {e}")
