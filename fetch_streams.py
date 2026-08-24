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

os.makedirs(output_dir, exist_ok=True)

def detect_real_format(content):
    """
    严格区分真实格式：
    1. 必须明确包含 M3U 头部标签才算 m3u
    2. 包含 #genre# 或标准的 名字,http 结构算 txt
    """
    content_str = content.strip()
    
    # 严格判断 M3U：必须带有 #EXTM3U 标签
    if "#EXTM3U" in content_str:
        return "m3u"
    
    # 严格判断 TXT：包含 #genre# 分类标签，或者多行符合 "名字,http..." 格式
    if "#genre#" in content_str:
        return "txt"
    
    lines = content_str.splitlines()
    txt_match_count = 0
    for line in lines:
        line = line.strip()
        # 检查是否为典型的 "名字,http" 结构
        if ',' in line and not line.startswith('#'):
            parts = line.split(',', 1)
            if len(parts) == 2 and ('http://' in parts[1] or 'https://' in parts[1] or 'p2p://' in parts[1] or '[组' in parts[1]):
                txt_match_count += 1
                if txt_match_count >= 2:  # 只要匹配到至少2行这样的格式，即可稳妥认定是 txt 电视台列表
                    return "txt"
                    
    # 如果有 #EXTINF: 但没有 #EXTM3U，也可以算 m3u
    if "#EXTINF:" in content_str:
        return "m3u"
        
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
    
    # m3u 使用 h 计数，txt 使用 k 计数，严格独立
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
                    
                    # 1. 原始文件统一放入 downloads
                    raw_download_path = os.path.join(output_dir, f"download_{index+1}.txt")
                    with open(raw_download_path, "w", encoding="utf-8", errors="ignore") as raw_out:
                        raw_out.write(content)

                    # 2. 深度且严格地分析真实内容格式
                    real_type = detect_real_format(content)
                    
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

                    # 3. 如果是合规的格式，存入 special_files 并赋予【正确的后缀】
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
                        
                        safe_print(f"   ✨ [成功分拣] 内容实为 {real_type.upper()} -> 规范保存为 special_files/{file_name}")
                    else:
                        safe_print(f"   ⚠️ [跳过] 内容为纯网页HTML或非标准源（已留在 downloads）")
                        
            except Exception as e:
                safe_print(f"   ⚠️ 访问失败: {e}")

    # 保存最终的 Lives JSON
    with open("lives_output.json", "w", encoding="utf-8") as jf:
        json.dump(json_output, jf, indent=2, ensure_ascii=False)
    safe_print("\n✨ 全部处理完毕！格式已严格分离，TXT 会正确归类为 k 开头并以 .txt 结尾。")

if __name__ == "__main__":
    run_scraper("202608100451.csv")
