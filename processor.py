import os
import re
import requests
import concurrent.futures
import sys
from urllib.parse import urlparse

# ================= ⚡ 跨库核心动态路径锁定 =================
WORKSPACE = os.environ.get("LIVE_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOWNLOADS_DIR = os.path.join(WORKSPACE, "downloads")  # 指向下载/解析的 txt 文件夹

# 四种目标大文件的输出路径
OUTPUT_HLS = os.path.join(WORKSPACE, "output_hls.txt")
OUTPUT_TS = os.path.join(WORKSPACE, "output_ts.txt")
OUTPUT_NEWLIVE = os.path.join(WORKSPACE, "output_newlive.txt")
OUTPUT_ALL_IP = os.path.join(WORKSPACE, "output_all_ip.txt")
# ==========================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def is_tvbox_or_json_file(file_path):
    """
    智能检测并识别是否为 TVBox 接口分享文件、JSON 配置文件或非纯直播源文件
    """
    file_name = os.path.basename(file_path).lower()
    
    # 1. 名称特征拦截
    tvbox_keywords = ["tvbox", "config", "json", "api", "sub", "setting", "interface"]
    if any(kw in file_name for kw in tvbox_keywords):
        return True

    # 2. 内容特征拦截（读取前 500 个字符检查是否为 JSON 结构）
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            header_snippet = f.read(500).strip()
            # 如果文件以 { 或 [ 开头，或者包含典型的 TVBox 结构字段，判定为 TVBox/JSON 配置文件
            if header_snippet.startswith(("{", "[")) or '"sites"' in header_snippet or '"lives"' in header_snippet:
                return True
    except Exception:
        pass

    return False

def parse_txt_or_m3u(file_path):
    """
    安全解析纯 txt 或 m3u 直播源文件
    """
    channels = []
    file_name = os.path.basename(file_path)
    
    # 先做安全防崩拦截：如果是 TVBox/JSON 配置文件，直接跳过
    if is_tvbox_or_json_file(file_path):
        print(f"🛡️ [安全拦截] 发现 TVBox/JSON 配置文件，已自动跳过: {file_name}", flush=True)
        return channels

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 匹配常规 m3u 格式 (EXTINF + URL)
        m3u_pattern = r'#EXTINF:.*?,(.*?)\n(https?://[^\s,\"\']+)'
        m3u_items = re.findall(m3u_pattern, content)
        if m3u_items:
            for name, url in m3u_items:
                channels.append({"name": name.strip(), "url": url.strip()})

        # 匹配普通文本格式 (名称,URL 或 名称 URL)
        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "http" not in line:
                continue
            
            # 如果单行太长（超过 500 字符），极可能是非法的混淆文本或配置代码，直接跳过防崩
            if len(line) > 500:
                continue

            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url})
            else:
                parts = line.split()
                if len(parts) >= 2 and parts[-1].startswith("http"):
                    name = " ".join(parts[:-1]).strip()
                    url = parts[-1].strip()
                    channels.append({"name": name, "url": url})
                    
        print(f"📄 [文件解析成功] {file_name} -> 提取到 {len(channels)} 条有效直播源", flush=True)
    except Exception as e:
        print(f"❌ [文件解析报错] {file_name} 出错: {e}", flush=True)
    
    return channels

def run_processor():
    print(f"==================================================", flush=True)
    print(f"🚀 开始执行直播源智能分类与IP聚合任务", flush=True)
    print(f"📂 目标文件夹路径: {DOWNLOADS_DIR}", flush=True)
    print(f"==================================================", flush=True)

    if not os.path.exists(DOWNLOADS_DIR):
        print(f"❌ 致命错误: 找不到目标目录 {DOWNLOADS_DIR}", flush=True)
        sys.exit(1)

    all_files = os.listdir(DOWNLOADS_DIR)
    target_files = [os.path.join(DOWNLOADS_DIR, f) for f in all_files if f.lower().endswith((".txt", ".m3u", ".json"))]
    
    print(f"📊 文件夹内总文件数: {len(all_files)} 个 | 待检查文件数: {len(target_files)} 个", flush=True)
    print(f"--------------------------------------------------", flush=True)

    hls_groups = {}     
    ts_groups = {}      
    newlive_groups = {} 
    
    all_ip_ports_set = set()
    total_links_found = 0
    stats_matched = {"hls": 0, "ts": 0, "newlive": 0, "ignored": 0}

    for file_path in target_files:
        channels = parse_txt_or_m3u(file_path)
        for ch in channels:
            name = ch.get("name", "未知频道")
            url = ch.get("url", "")
            if not url:
                continue

            total_links_found += 1
            parsed_url = urlparse(url)
            host = parsed_url.netloc  
            path = parsed_url.path + (f"?{parsed_url.query}" if parsed_url.query else "")

            if not host:
                stats_matched["ignored"] += 1
                continue

            matched = False
            if "/hls/" in path and path.endswith("index.m3u8"):
                if host not in hls_groups:
                    hls_groups[host] = []
                hls_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)
                stats_matched["hls"] += 1
                matched = True

            elif "/tsfile/live/" in path:
                if host not in ts_groups:
                    ts_groups[host] = []
                ts_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)
                stats_matched["ts"] += 1
                matched = True

            elif "/newlive/live/hls/" in path:
                if host not in newlive_groups:
                    newlive_groups[host] = []
                newlive_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)
                stats_matched["newlive"] += 1
                matched = True
            
            if not matched:
                stats_matched["ignored"] += 1

    print(f"--------------------------------------------------", flush=True)
    print(f"📈 【检索统计看板】", flush=True)
    print(f"   - 总扫描有效链接数 : {total_links_found} 条", flush=True)
    print(f"   - 命中 HLS 特征源  : {stats_matched['hls']} 条", flush=True)
    print(f"   - 命中 TS  特征源  : {stats_matched['ts']} 条", flush=True)
    print(f"   - 命中 NewLive源   : {stats_matched['newlive']} 条", flush=True)
    print(f"   - 不符合特征忽略源 : {stats_matched['ignored']} 条", flush=True)
    print(f"   - 聚合独立 IP+端口 : {len(all_ip_ports_set)} 个", flush=True)
    print(f"--------------------------------------------------", flush=True)

    def write_grouped_file(filepath, groups_dict, title_tag):
        print(f"✍️ 正在写入 {title_tag} 总表 -> 包含 {len(groups_dict)} 个独立 IP 组", flush=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# ==========================================\n")
            f.write(f"# 📺 {title_tag} 直播源聚合总表\n")
            f.write(f"# ==========================================\n\n")
            for host, chs in groups_dict.items():
                f.write(f"{host},#genre#\n")
                seen_paths = set()
                for c in chs:
                    if c['path'] not in seen_paths:
                        seen_paths.add(c['path'])
                        f.write(f"{c['name']},http://{host}{c['path']}\n")
                f.write("\n")

    write_grouped_file(OUTPUT_HLS, hls_groups, "HLS类直播源")
    write_grouped_file(OUTPUT_TS, ts_groups, "TS类直播源")
    write_grouped_file(OUTPUT_NEWLIVE, newlive_groups, "NewLive类直播源")

    print(f"✍️ 正在写入纯 IP+端口 汇总表 -> 共计 {len(all_ip_ports_set)} 个唯一地址", flush=True)
    with open(OUTPUT_ALL_IP, "w", encoding="utf-8") as f:
        f.write("# ==========================================\n")
        f.write("# 🌐 命中目标特征的全部 IP+端口 汇总清单\n")
        f.write("# ==========================================\n\n")
        for ip_port in sorted(list(all_ip_ports_set)):
            f.write(f"{ip_port}\n")

    print(f"==================================================", flush=True)
    print(f"🎉 全部任务圆满成功！", flush=True)
    print(f"==================================================", flush=True)

if __name__ == "__main__":
    run_processor()
