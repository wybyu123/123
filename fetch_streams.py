import os
import csv
import requests
import json
import datetime
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 配置文件夹
output_dir = "downloads"
special_dir = "special_files"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(special_dir, exist_ok=True)

def is_m3u(content):
    """严格判断：必须包含 M3U 的标准头部或标签"""
    return "#EXTM3U" in content or "#EXTINF:" in content

def is_txt_tv_list(content):
    """严格判断：包含 #genre# 或符合 频道名,http 结构的文本源"""
    if "#genre#" in content:
        return True
    # 检查是否有至少一行符合 "名字,http" 的直播源结构
    lines = content.splitlines()
    match_count = 0
    for line in lines:
        line = line.strip()
        if ',' in line and ('http://' in line or 'https://' in line or '[' in line):
            match_count += 1
            if match_count >= 1:  # 只要匹配到1行以上就认为是这类直播源
                return True
    return False

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
    
    # 【修改点 1】m3u 使用 h 计数，txt 使用 k 计数，分开计算
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
            
            safe_print(f"🔗 正在处理: {url}")
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=8)
                response.encoding = response.apparent_encoding if response.apparent_encoding else 'utf-8'
                
                if response.status_code == 200:
                    content = response.text
                    
                    # 【修改点 2】精准鉴别内容格式
                    is_m3u_file = is_m3u(content)
                    is_txt_file = is_txt_tv_list(content)
                    
                    if is_m3u_file or is_txt_file:
                        if is_m3u_file:
                            ext = ".m3u"
                            count_str = f"h{m3u_count:02d}"  # M3U 使用 h 字母
                            m3u_count += 1
                        else:
                            ext = ".txt"
                            count_str = f"k{txt_count:02d}"  # TXT 使用 k 字母
                            txt_count += 1
                        
                        file_name = f"{date_str}{count_str}{ext}"
                        file_path = os.path.join(special_dir, file_name)
                        
                        with open(file_path, "w", encoding="utf-8") as out:
                            out.write(content)
                        
                        # 生成 GitHub Raw 直链
                        raw_url = f"https://raw.githubusercontent.com/wybyu123/123/main/{special_dir}/{file_name}"

                        json_output["lives"].append({
                            "type": 0,
                            "epg": "http://epg.52sw.top:668/?ch={name}&date={date}",
                            "logo": "https://gongdian.top/tv/taibiao/{name}.png",
                            "playerType": 2,
                            "timeout": 10,
                            "name": f"源_{date_str}{count_str}",
                            "url": raw_url 
                        })
                        
                        safe_print(f"✅ 已精准分类并存入 special_files: {file_name}")
                    else:
                        # 其他无关网页或接口存入 downloads
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
