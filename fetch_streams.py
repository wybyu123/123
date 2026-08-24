import os
import csv
import requests
import json
import datetime
import shutil
import sys
from urllib.parse import urlparse

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 配置文件夹路径
output_dir = "downloads"
special_dir = "special_files"

# 1. 每次运行脚本时，自动清空并重建 downloads 和 special_files 目录，避免旧文件堆积
for d in [output_dir, special_dir]:
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)

def detect_real_format_by_ratio(content):
    """
    通过计算内容中不同特征的行数比例来精确判断真实格式
    """
    content_str = content.strip()
    lines = content_str.splitlines()
    
    m3u_score = 0
    txt_score = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 统计 M3U 特征
        if line.startswith("#EXTM3U") or line.startswith("#EXTINF:"):
            m3u_score += 2
        elif ".m3u8" in line or ".ts" in line:
            m3u_score += 1
            
        # 统计 TXT 特征
        if "#genre#" in line:
            txt_score += 5
        elif ',' in line and not line.startswith('#'):
            parts = line.split(',', 1)
            if len(parts) == 2 and ('http://' in parts[1] or 'https://' in parts[1] or 'p2p://' in parts[1] or '[' in parts[1]):
                txt_score += 1

    if txt_score > m3u_score:
        return "txt"
    elif m3u_score > txt_score:
        return "m3u"
    else:
        if "#EXTM3U" in content_str:
            return "m3u"
        if "#genre#" in content_str:
            return "txt"
            
    return "other"

def get_safe_filename_from_url(url, index):
    """
    从 URL 提取主机名作为文件名，并将冒号、斜杠等不安全字符替换为下划线或横杠
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc if parsed.netloc else parsed.path
        # 替换不合法的路径字符
        safe_name = netloc.replace(":", "-").replace("/", "-").replace("\\", "-")
        if not safe_name:
            safe_name = f"site_{index}"
        return safe_name
    except Exception:
        return f"site_{index}"

def safe_print(text):
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
    
    json_output = {"lives": []}
    
    with open(csv_file, mode="r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        next(reader, None) # 跳过表头
        
        for index, row in enumerate(reader):
            if not row: 
                continue
            host_val = row[0].strip()
            url = host_val if host_val.startswith("http") else f"http://{host_val}"
            
            safe_print(f"🔗 正在处理 [{index+1}]: {url}")
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                # 允许自动重定向，解决部分直接下载或重定向链接抓取不到的问题
                response = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
                response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                
                if response.status_code == 200:
                    content = response.text
                    
                    # 根据 URL 动态生成 downloads 下的文件名（将 IP:端口 或 域名 中的特殊符号替换为 -）
                    base_name = get_safe_filename_from_url(url, index+1)
                    raw_download_path = os.path.join(output_dir, f"{base_name}.txt")
                    
                    with open(raw_download_path, "w", encoding="utf-8", errors="ignore") as raw_out:
                        raw_out.write(content)

                    # 格式判断
                    real_type = detect_real_format_by_ratio(content)
                    
                    ext = None
                    count_str = ""
                    if real_type == "m3u":
                        ext = ".m3u"
                        count_str = f"h{m3u_count:02d}"
                        m3u_count += 1
                    elif real_type == "txt":
                        ext = ".txt"
                        count_str = f"k{txt_count:02d}"
                        txt_count += 1

                    if ext:
                        file_name = f"{date_str}{count_str}{ext}"
                        file_path = os.path.join(special_dir, file_name)
                        
                        with open(file_path, "w", encoding="utf-8") as out:
                            out.write(content)
                        
                        raw_url = f"https://raw.githubusercontent.com/wybyu123/123/refs/heads/main/{special_dir}/{file_name}"

                        json_output["lives"].append({
                            "type": 0,
                            "epg": "http://epg.52sw.top:668/?ch={name}&date={date}",
                            "logo": "https://gongdian.top/tv/taibiao/{name}.png",
                            "playerType": 2,
                            "timeout": 10,
                            "name": f"源_{date_str}{count_str}",
                            "url": raw_url 
                        })
                        
                        safe_print(f"   ✨ [成功分拣] 识别为 {real_type.upper()} -> 存入 special_files/{file_name}")
                    else:
                        safe_print(f"   ⚠️ [跳过] 非标准格式（已作为原始文本保存至 downloads/{base_name}.txt）")
                        
            except Exception as e:
                safe_print(f"   ⚠️ 访问失败: {e}")

    # 保存最终 JSON
    with open("lives_output.json", "w", encoding="utf-8") as jf:
        json.dump(json_output, jf, indent=2, ensure_ascii=False)
    safe_print("\n✨ 全部处理完毕！downloads 和 special_files 均已实现每次自动清空与精准命名。")

if __name__ == "__main__":
    run_scraper("202608100451.csv")
