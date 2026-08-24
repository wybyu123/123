import os
import csv
import requests
import json
import datetime
import shutil
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 配置文件夹路径
output_dir = "downloads"
special_dir = "special_files"

# 1. 每次运行脚本时，直接清空并重建 special_files 目录，避免旧文件堆积
if os.path.exists(special_dir):
    shutil.rmtree(special_dir)
os.makedirs(special_dir, exist_ok=True)

# downloads 目录保留（可根据需要决定是否每次清空，这里保持目录存在）
os.makedirs(output_dir, exist_ok=True)

def detect_real_format(content):
    """
    深度分析内容，判断其真实格式：
    返回: 'm3u', 'txt', 或 'other'
    """
    content_str = content.strip()
    
    # 判读是否为 M3U 标准格式
    if "#EXTM3U" in content_str or "#EXTINF:" in content_str:
        return "m3u"
    
    # 判断是否为 TXT 直播源格式（含 #genre# 或 名字,http 结构）
    if "#genre#" in content_str:
        return "txt"
    
    lines = content_str.splitlines()
    match_count = 0
    for line in lines:
        line = line.strip()
        if ',' in line and ('http://' in line or 'https://' in line or '[组' in line or 'p2p://' in line):
            match_count += 1
            if match_count >= 1:  # 匹配到至少一行符合的直播源即判定为 txt 源
                return "txt"
                
    return "other"

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
    
    # m3u 使用 h 计数，txt 使用 k 计数，分开独立编号
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
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=10)
                response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                
                if response.status_code == 200:
                    content = response.text
                    
                    # 第一步：先将所有原始响应保存到 downloads 目录中，便于详细查看每个文件
                    raw_download_path = os.path.join(output_dir, f"download_{index+1}.txt")
                    with open(raw_download_path, "w", encoding="utf-8", errors="ignore") as raw_out:
                        raw_out.write(content)

                    # 第二步：对内容进行深度智能辨别（纠错格式，防止后缀名与实际内容不符）
                    real_type = detect_real_format(content)
                    
                    if real_type == "m3u":
                        ext = ".m3u"
                        count_str = f"h{m3u_count:02d}"
                        m3u_count += 1
                    elif real_type == "txt":
                        ext = ".txt"
                        count_str = f"k{txt_count:02d}"
                        txt_count += 1
                    else:
                        ext = None

                    # 第三步：如果识别为合格的 m3u 或 txt 直播源，则放入 special_files 统一管理并生成 JSON
                    if ext:
                        file_name = f"{date_str}{count_str}{ext}"
                        file_path = os.path.join(special_dir, file_name)
                        
                        with open(file_path, "w", encoding="utf-8") as out:
                            out.write(content)
                        
                        # 生成对应的 GitHub Raw 直链
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
                        
                        safe_print(f"   ✨ [成功分拣] 识别为 {real_type.upper()} 文件 -> 存入 special_files/{file_name}")
                    else:
                        safe_print(f"   ⚠️ [跳过] 内容为网页HTML或非标准直播源格式（已保留在 downloads）")
                        
            except Exception as e:
                safe_print(f"   ⚠️ 访问失败: {e}")

    # 保存最终的 Lives JSON 配置文件
    with open("lives_output.json", "w", encoding="utf-8") as jf:
        json.dump(json_output, jf, indent=2, ensure_ascii=False)
    safe_print("\n✨ 全部处理完毕！旧的 special_files 已清理，最新有效直链已生成至 lives_output.json。")

if __name__ == "__main__":
    run_scraper("202608100451.csv")
