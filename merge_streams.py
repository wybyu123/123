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
    name = re.sub(r'[\(\（].*?[\)\）]|\[.*?\]', '', name)
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
    """合并 TXT 文件：限制前8个、按文件名排序、按 URL 全局去重、清洗名称"""
    txt_files = glob.glob(os.path.join(special_dir, "*.txt"))
    if not txt_files:
        print("⚠️ 没有找到任何 TXT 文件用于合并。")
        return

    # 按文件名排序并限制只取前 8 个
    txt_files = sorted(txt_files)[:8]

    categories = {}  # 结构: { "分类名": [ (name, url), ... ] }
    seen_urls = set()  # 用于记录已经出现过的 URL，实现全局去重
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
                
                if is_update_line(line_str):
                    continue
                
                if "#genre#" in line_str:
                    genre_name = line_str.split(",")[0].strip()
                    if is_update_line(genre_name):
                        continue
                    current_genre = genre_name
                    if current_genre not in categories:
                        categories[current_genre] = []
                    continue
                
                if ',' in line_str and not line_str.startswith('#'):
                    parts = line_str.split(',', 1)
                    if len(parts) == 2:
                        raw_name, url = parts[0].strip(), parts[1].strip()
                        clean_name = clean_channel_name(raw_name)
                        
                        if not clean_name:
                            continue
                        
                        # 检查 URL 是否已经存在，若存在则跳过（去重）
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        
                        if current_genre not in categories:
                            categories[current_genre] = []
                        
                        categories[current_genre].append((clean_name, url))
        except Exception as e:
            print(f"⚠️ 读取 TXT 文件出错 {file_path}: {e}")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines = []

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
    print(f"✨ TXT 汇总文件已生成（已限制前8个并去重）: {output_path}")

def merge_m3u_files():
    """合并 M3U 文件：限制前8个、按文件名排序、按 URL 全局去重、清洗名称"""
    m3u_files = glob.glob(os.path.join(special_dir, "*.m3u"))
    if not m3u_files:
        print("⚠️ 没有找到任何 M3U 文件用于合并。")
        return

    # 按文件名排序并限制只取前 8 个
    m3u_files = sorted(m3u_files)[:8]

    header_info = '#EXTM3U x-tvg-url="http://8.153.108.11:8080/epg/epg.gz"'
    groups = {}  # 结构: { "分类名": [ (extinf_line, url_line), ... ] }
    seen_urls = set()  # URL 全局去重集合

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
                    
                    # 检查 M3U 链接是否重复
                    if url_line in seen_urls:
                        continue
                    seen_urls.add(url_line)
                        
                    group_match = re.search(r'group-title="([^"]+)"', extinf_line)
                    group_name = group_match.group(1) if group_match else "其他频道"
                    
                    if is_update_line(group_name):
                        continue
                        
                    parts = extinf_line.split(',', 1)
                    if len(parts) == 2:
                        raw_title = parts[1]
                        clean_title = clean_channel_name(raw_title)
                        if not clean_title:
                            continue
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
    print(f"✨ M3U 汇总文件已生成（已限制前8个并去重）: {output_path}")

if __name__ == "__main__":
    print("🚀 开始执行深度合并、限制前8个与去重清洗任务...")
    merge_txt_files()
    merge_m3u_files()
    print("✨ 所有任务圆满完成！")
