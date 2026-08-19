import os
import csv
import requests
import json
import datetime
import sys

# 强制标准输出使用 UTF-8 编码，防止中文或符号乱码
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 配置文件夹
output_dir = "downloads"
special_dir = "special_files"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(special_dir, exist_ok=True)

def is_m3u(content):
    return "#EXTM3U" in content or "#EXTINF" in content

def is_txt_tv_list(content):
    # 检查是否包含特殊标识或典型的 "名称,地址" 结构
    return "#genre#" in content or (',' in content and 'http' in content)

def safe_print(text):
    """安全打印函数，过滤掉可能导致编码崩溃的特殊符号"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'ignore').decode('ascii'))

def run_scraper(csv_file):
    if not os.path.exists(csv_file):
        safe_print(f"❌ 错误: 找不到文件 {csv_file}")
        return

    date_str = datetime.datetime.now().strftime("%m%d")
    m3u_count = 1
    txt_count = 1
    
    # 初始化 JSON 结构
    json_output = {"lives": []}
    
    # 【核心修复】：明确指定 utf-8-sig 以完美兼容带有 BOM 或特殊字符的 CSV 文件
    with open(csv_file, mode="r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        next(reader, None) # 跳过表头
        
        for index, row in enumerate(reader):
            if not row: 
                continue
            host_val = row[0].strip()
            url = host_val if host_val.startswith("http") else f"http://{host_val}"
            
            safe_print(f"🔗 正在处理: {url}")
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=8)
                
                # 自动识别并纠正网页响应编码，防止下载下来的文本乱码
                response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                
                if response.status_code == 200:
                    content = response.text
                    is_m3u_file = is_m3u(content)
                    is_txt_file = is_txt_tv_list(content)
                    
                    # 判断是否为我们要的直播源文件
                    if is_m3u_file or is_txt_file:
                        ext = ".m3u" if is_m3u_file else ".txt"
                        count = m3u_count if is_m3u_file else txt_count
                        file_name = f"{date_str}h{count:02d}{ext}"
                        file_path = os.path.join(special_dir, file_name)
                        
                        # 统一使用 utf-8 写入文件
                        with open(file_path, "w", encoding="utf-8") as out:
                            out.write(content)
                        
                        # 转换为 GitHub Raw 直链
                        raw_url = f"https://raw.githubusercontent.com/wybyu123/123/main/{special_dir}/{file_name}"

                        json_output["lives"].append({
                            "type": 0,
                            "epg": "http://epg.52sw.top:668/?ch={name}&date={date}",
                            "logo": "https://gongdian.top/tv/taibiao/{name}.png",
                            "playerType": 2,
                            "timeout": 10,
                            "name": f"源_{date_str}h{count:02d}",
                            "url": raw_url 
                        })
                        
                        if is_m3u_file: 
                            m3u_count += 1
                        else: 
                            txt_count += 1
                        safe_print(f"✅ 已存入 special_files: {file_name}")
                    else:
                        # 非直播源文件存入 downloads
                        save_path = os.path.join(output_dir, f"other_{index}.txt")
                        with open(save_path, "w", encoding="utf-8", errors="ignore") as out:
                            out.write(content)
                            
            except Exception as e:
                safe_print(f"⚠️ 访问失败: {e}")

    # 保存 JSON 文件
    with open("lives_output.json", "w", encoding="utf-8") as jf:
        json.dump(json_output, jf, indent=2, ensure_ascii=False)
    safe_print("\n✨ 全部处理完毕，JSON 已生成。")

if __name__ == "__main__":
    run_scraper("202608100451.csv")
