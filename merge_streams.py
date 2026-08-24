import os
import glob
import re
import datetime
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

special_dir = "special_files"

def clean_line(line):
    return line.strip()

def is_update_line(line):
    """判断是否为更新时间相关的行或分类"""
    keywords = ["更新时间", "更新", "2026-", "2025-"]
    for kw in keywords:
        if kw in line:
            return True
    return False

def merge_txt_files():
    """合并所有 TXT 文件，按分类精确归组，自动过滤并重新生成更新时间"""
    txt_files = glob.glob(os.path.join(special_dir, "*.txt"))
    if not txt_files:
        print("⚠️ 没有找到任何 TXT 文件用于合并。")
        return

    categories = {}  # 结构: { "央视频道": [ (name, url), ... ] }
    current_genre = "默认分类"
    categories[current_genre] = []
    
    first_url_per_category = {} # 记录每个分类的第一个链接，用于生成更新时间

    for file_path in txt_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                
                # 过滤掉原有的更新时间行
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
                        name, url = parts[0].strip(), parts[1].strip()
                        if current_genre not in categories:
                            categories[current_genre] = []
                        
                        categories[current_genre].append((name, url))
                        
                        # 记录该分类的第一个链接
                        if current_genre not in first_url_per_category:
                            first_url_per_category[current_genre] = url
        except Exception as e:
            print(f"⚠️ 读取 TXT 文件出错 {file_path}: {e}")

    # 生成合并后的 TXT 内容
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines = []

    for genre, items in categories.items():
        if not items:
            continue
        
        output_lines.append(f"{genre},#genre#")
        
        # 使用该分类的第一个链接自动生成一个更新时间提示项
        first_url = first_url_per_category.get(genre, "http://183.203.166.28:9003/hls/1/index.m3u8")
        output_lines.append(f"📅 更新于 {now_str},{first_url}")
        
        for name, url in items:
            output_lines.append(f"{name},{url}")

    output_path = "merged_channels.txt"
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("\n".join(output_lines) + "\n")
    print(f"✨ TXT 汇总文件已生成: {output_path}")

def merge_m3u_files():
    """合并所有 M3U 文件，按 group-title 精准分类，过滤旧更新时间并插入新更新时间"""
    m3u_files = glob.glob(os.path.join(special_dir, "*.m3u"))
    if not m3u_files:
        print("⚠️ 没有找到任何 M3U 文件用于合并。")
        return

    # 提取 M3U 头部全局信息（取第一个文件的头部）
    header_info = '#EXTM3U x-tvg-url="http://8.153.108.11:8080/epg/epg.gz"'
    
    groups = {}  # 结构: { "分类名": [ (extinf_line, url_line), ... ] }
    first_url_per_group = {}

    for file_path in m3u_files:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXTINF:"):
                    # 检查并过滤包含更新时间的项
                    if is_update_line(line):
                        i += 2  # 跳过这行和它的url
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
                        
                    # 提取 group-title 作为分类标记（完全一样归一组，有细微差别独立成组）
                    group_match = re.search(r'group-title="([^"]+)"', extinf_line)
                    group_name = group_match.group(1) if group_match else "其他频道"
                    
                    if is_update_line(group_name):
                        continue
                        
                    if group_name not in groups:
                        groups[group_name] = []
                        
                    groups[group_name].append((extinf_line, url_line))
                    
                    if group_name not in first_url_per_group:
                        first_url_per_group[group_name] = url_line
                else:
                    i += 1
        except Exception as e:
            print(f"⚠️ 读取 M3U 文件出错 {file_path}: {e}")

    # 生成合并后的 M3U 内容
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines = [header_info]

    for group_name, items in groups.items():
        if not items:
            continue
            
        first_url = first_url_per_group.get(group_name, "http://gslbserv.itv.cmvideo.cn:80/1.m3u8")
        
        # 自动生成一个带有更新时间的提示频道
        update_extinf = f'#EXTINF:-1 tvg-id="Update" tvg-name="更新时间" group-title="{group_name}",📅 更新于 {now_str}'
        output_lines.append(update_extinf)
        output_lines.append(first_url)
        
        for extinf, url in items:
            output_lines.append(extinf)
            output_lines.append(url)

    output_path = "merged_channels.m3u"
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("\n".join(output_lines) + "\n")
    print(f"✨ M3U 汇总文件已生成: {output_path}")

if __name__ == "__main__":
    print("🚀 开始执行合并任务...")
    merge_txt_files()
    merge_m3u_files()
    print("✨ 所有汇总任务圆满完成！")
