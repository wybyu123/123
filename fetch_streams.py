import os
import csv
import requests
import sys

# 关键点 1：强制标准输出实时刷新，不带缓冲，这样在日志中能立刻看到打印内容
sys.stdout.reconfigure(line_buffering=True)

output_dir = "downloads"
os.makedirs(output_dir, exist_ok=True)

csv_file = "202608100451.csv"

if not os.path.exists(csv_file):
    print(f"❌ 错误: 找不到文件 {csv_file}")
    exit(1)

print(f"📂 成功加载列表文件: {csv_file}")

with open(csv_file, mode="r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader, None)  # 读取表头
    print(f"📋 表头信息: {header}")
    
    rows = list(reader)
    total_rows = len(rows)
    print(f"📊 总共需要处理的网址/节点数: {total_rows}\n" + "-"*40)
    
    for index, row in enumerate(rows):
        if not row:
            continue
        host_val = row[0].strip()
        
        # 智能补全 URL 协议
        if host_val.startswith("http://") or host_val.startswith("https://"):
            url = host_val
        else:
            url = f"http://{host_val}"
            
        print(f"[{index+1}/{total_rows}] 🔗 正在访问: {url}")
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # 设置 8 秒超时，防止死链接卡死
            response = requests.get(url, headers=headers, timeout=8)
            
            print(f"   📥 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                safe_name = host_val.replace("://", "_").replace("/", "_").replace(":", "_")
                file_path = os.path.join(output_dir, f"result_{index+1}_{safe_name}.txt")
                
                with open(file_path, "w", encoding="utf-8", errors="ignore") as out:
                    out.write(response.text)
                print(f"   ✅ 成功保存文件 -> {file_path} (大小: {len(response.text)} 字符)")
            else:
                print(f"   ⚠️ 访问异常，跳过。状态码: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"   ⏰ 连接超时: {url}")
        except requests.exceptions.ConnectionError:
            print(f"   🔌 连接拒绝/无法到达: {url}")
        except Exception as e:
            print(f"   ❌ 其他错误: {e}")
        
        print("-" * 40)

print("✨ 全部节点处理完毕！")
