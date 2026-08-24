import os
import glob
import re
import datetime
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

special_dir = "special_files"

def clean_channel_name(name):
    """
    清洗频道名称：
    1. 去除开头的特殊符号如 ❤️, *, 等
    2. 去除括号及内部内容（如 (720p), [Geo-blocked] 等）
    """
    # 去除圆括号、方括号及其中内容
    name = re.sub(r'[\(\（].*?[\)\）]|\[.*?\]', '', name)
    # 去除开头常见的装饰符号、爱心、星号等
    name = re.sub(r'^[❤️⭐★☆\*\s]+', '', name)
    return name.strip()

def is_update_line(line):
    """判断是否为旧的更新时间相关的行或分类"""
    keywords = ["更新时间", "更新", "2026-", "2025-"]
    for kw in keywords:
        if kw in line:
            return True
    return False

def merge_txt_files():
    """合并所有 TXT 文件，清洗频道名称与括号，全局顶部仅显示一次更新时间"""
    txt_files = glob.glob(os.path.join(special_dir, "*.txt"))
    if not txt_files:
        print("⚠️ 没有找到任何 TXT 文件用于合并。")
        return

    categories = {}  # 结构: { "分类名": [ (name, url), ... ] }
    current_genre = "默认分类"
    categories[current_genre] = []

    for file_path in txt_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                
                # 过滤掉旧的更新时间行
                if is_update_line(line_str):
                    continue
                
                # 检测 TXT 分类标签
                if "#genre#" in line_str:
                    genre_name = line_str.split(",")[0].strip()
                    if is_update_line(genre_name):
                        continue
                    current_genre = genre_name
                    if current_genre not in categories:
                        categories[current_genre] = []
                    continue
                
                # 解析频道行 (名字,url)
                if ',' in line_str and not line_str.startswith('#'):
                    parts = line_str.split(',', 1)
                    if len(parts) == 2:
                        raw_name, url = parts[0].strip(), parts[1].strip()
                        clean_name = clean_channel_name(raw_name)
                        
                        # 如果清洗后名字为空，则跳过
                        if not clean_name:
                            continue
                            
                        if current_genre not in categories:
                            categories[current_genre] = []
                        
                        categories[current_genre].append((clean_name, url))
        except Exception as e:
            print(f"⚠️ 读取 TXT 文件出错 {file_path}: {e}")

    # 生成合并后的 TXT 内容
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines = []

    # 全局顶部生成一次更新时间项
    output_lines.append(f"更新时间,#genre#")
    output_lines.append(f"📅 汇总更新于 {now_str},http://183.203.166.28:9003/hls/1/index.m3u8")

    for genre, items in categories.items():
        if not items:
            continue
        
        output_lines.append(f"{genre},#genre#")
        
        for name, url in items:
            output_lines.append(f"{name},{url}")

    output_path = "merged_channels.txt"
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("\n".join(output_lines) + "\n")
    print(f"✨ TXT 汇总文件已生成: {output_path}")

def merge_m3u_files():
    """合并所有 M3U 文件，清洗名字与括号，全局顶部仅显示一次更新时间"""
    m3u_files = glob.glob(os.path.join(special_dir, "*.m3u"))
    if not m3u_files:
        print("⚠️ 没有找到任何 M3U 文件用于合并。")
        return

    header_info = '#EXTM3U x-tvg-url="http://8.153.108.11:8080/epg/epg.gz"'
    groups = {}  # 结构: { "分类名": [ (extinf_line, url_line), ... ] }

    for file_path in m3u_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF:"):
                    if is_update_line(line):
                        i += 2
                        continue
                        
                    extinf_line = line
                    url_line = ""
                    
                    if i + 1 < len(lines):
                        url_line = lines[i+1].strip()
                        i += 2
                    else:
                        i += 1
                        
                    if not url_line or url_line.startswith("#"):
                        continue
                        
                    group_match = re.search(r'group-title="([^"]+)"', extinf_line)
                    group_name = group_match.group(1) if group_match else "其他频道"
                    
                    if is_update_line(group_name):
                        continue
                        
                    # 提取并清洗频道名称（逗号后面的部分为显示名称）
                    parts = extinf_line.split(',', 1)
                    if len(parts) == 2:
                        raw_title = parts[1]
                        clean_title = clean_channel_name(raw_title)
                        if not clean_title:
                            i += 0
                            continue
                        # 重新组装 EXTINF 行，应用清洗后的名字
                        extinf_line = f"{parts[0]},{clean_title}"
                        
                    if group_name not in groups:
                        groups[group_name] = []
                        
                    groups[group_name].append((extinf_line, url_line))
                else:
                    i += 1
        except Exception as e:
            print(f"⚠️ 读取 M3U 文件出错 {file_path}: {e}")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines = [header_info]

    # 全局顶部插入一次更新时间频道
    update_extinf = f'#EXTINF:-1 tvg-id="Update" tvg-name="更新时间" group-title="更新时间",📅 汇总更新于 {now_str}'
    update_url = "http://gslbserv.itv.cmvideo.cn:80/1.m3u8?channel-id=bestzb"
    output_lines.append(update_extinf)
    output_lines.append(update_url)

    for group_name, items in groups.items():
        if not items:
            continue
        
        for extinf, url in items:
            output_lines.append(extinf)
            output_lines.append(url)

    output_path = "merged_channels.m3u"
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("\n".join(output_lines) + "\n")
    print(f"✨ M3U 汇总文件已生成: {output_path}")

if __name__ == "__main__":
    print("🚀 开始执行深度合并与清洗任务...")
    merge_txt_files()
    merge_m3u_files()
    print("✨ 所有汇总与清洗任务圆满完成！")
