import os
import re
import sys
import requests
import concurrent.futures
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

def fix_mojibake(text):
    """
    智能修复由于编码错位产生的中文乱码（如 CCTV-å¨±ä¹ -> CCTV-娱乐）
    """
    if not text:
        return ""
    text = text.strip()
    try:
        # 尝试通过 latin1 编码回字节，再用 utf-8 解码还原中文
        fixed = text.encode('latin1').decode('utf-8')
        return fixed
    except Exception:
        return text

def is_tvbox_or_json_file(file_path):
    """
    智能检测并识别是否为 TVBox 接口分享文件、JSON 配置文件或非纯直播源文件
    """
    file_name = os.path.basename(file_path).lower()
    tvbox_keywords = ["tvbox", "config", "json", "api", "sub", "setting", "interface"]
    if any(kw in file_name for kw in tvbox_keywords):
        return True

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            header_snippet = f.read(500).strip()
            if header_snippet.startswith(("{", "[")) or '"sites"' in header_snippet or '"lives"' in header_snippet:
                return True
    except Exception:
        pass

    return False

def clean_url(url):
    """
    清理 URL：如果包含 $ 符号，截断 $ 符号及后面的所有注释内容
    """
    if not url:
        return ""
    if "$" in url:
        url = url.split("$", 1)[0]
    return url.strip()

def parse_txt_or_m3u(file_path):
    channels = []
    file_name = os.path.basename(file_path)
    
    if is_tvbox_or_json_file(file_path):
        print(f"🛡️ [安全拦截] 发现 TVBox/JSON 配置文件，已自动跳过: {file_name}", flush=True)
        return channels

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        m3u_pattern = r'#EXTINF:.*?,(.*?)\n(https?://[^\s,\"\']+)'
        m3u_items = re.findall(m3u_pattern, content)
        if m3u_items:
            for name, url in m3u_items:
                clean_u = clean_url(url)
                fixed_name = fix_mojibake(name)
                if clean_u and fixed_name:
                    channels.append({"name": fixed_name, "url": clean_u})

        lines = content.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "http" not in line:
                continue
            
            if len(line) > 500:
                continue

            if "," in line:
                parts = line.split(",", 1)
                name = fix_mojibake(parts[0])
                url = clean_url(parts[1])
                if url.startswith("http") and name:
                    channels.append({"name": name, "url": url})
            else:
                parts = line.split()
                if len(parts) >= 2 and parts[-1].startswith("http"):
                    name = fix_mojibake(" ".join(parts[:-1]))
                    url = clean_url(parts[-1])
                    if url.startswith("http") and name:
                        channels.append({"name": name, "url": url})
                    
        print(f"📄 [文件解析成功] {file_name} -> 提取到 {len(channels)} 条有效直播源", flush=True)
    except Exception as e:
        print(f"❌ [文件解析报错] {file_name} 出错: {e}", flush=True)
    
    return channels

def get_channel_sort_key(channel_item):
    name = channel_item.get("name", "")
    m = re.search(r'CCTV[- ]?(\d+)', name, re.IGNORECASE)
    if m:
        return (0, int(m.group(1)), name)
    elif "卫视" in name:
        return (1, 0, name)
    else:
        return (2, 0, name)

def fetch_json_channels(host):
    """
    (TS类) 尝试访问 http://host/iptv/live/1000.json?key=txipt 获取对应 IP 的频道信息并解析
    """
    test_url = f"http://{host}/iptv/live/1000.json?key=txipt"
    discovered_channels = []
    try:
        r = requests.get(test_url, headers=HEADERS, timeout=3)
        if r.status_code == 200:
            data = r.json()
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ["channels", "list", "data", "result"]:
                    if k in data and isinstance(data[k], list):
                        items = data[k]
                        break
                if not items:
                    for v in data.values():
                        if isinstance(v, list):
                            items = v
                            break

            for item in items:
                if isinstance(item, dict):
                    raw_name = item.get("name") or item.get("title") or item.get("ChannelName")
                    name = fix_mojibake(raw_name)
                    url = item.get("url") or item.get("link") or item.get("PlayUrl")
                    if name and url:
                        discovered_channels.append({"name": name, "url": clean_url(url)})
    except Exception:
        pass
    return host, discovered_channels

def fetch_zhgxtv_channels(host):
    """
    (HLS类) 访问 http://host/ZHGXTV/Public/json/live_interface.txt
    解析里面的频道列表，并将其中包含的内网 IP 替换为当前外网 host
    """
    test_url = f"http://{host}/ZHGXTV/Public/json/live_interface.txt"
    discovered_channels = []
    try:
        r = requests.get(test_url, headers=HEADERS, timeout=3)
        if r.status_code == 200:
            content = r.text
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or "http" not in line:
                    continue
                
                if "," in line:
                    parts = line.split(",", 1)
                    name = fix_mojibake(parts[0])
                    url = clean_url(parts[1])
                else:
                    parts = line.split()
                    if len(parts) >= 2 and parts[-1].startswith("http"):
                        name = fix_mojibake(" ".join(parts[:-1]))
                        url = clean_url(parts[-1])
                    else:
                        continue

                if name and url.startswith("http"):
                    parsed_sub = urlparse(url)
                    path_query = parsed_sub.path + (f"?{parsed_sub.query}" if parsed_sub.query else "")
                    new_url = f"http://{host}{path_query}"
                    discovered_channels.append({"name": name, "url": new_url})
    except Exception:
        pass
    return host, discovered_channels

def enhance_output_ts_from_json():
    if not os.path.exists(OUTPUT_TS):
        return

    print(f"\n🔍 【TS类智能探测与补全】开始对 output_ts.txt 中的 IP 列表进行 API 探测与补全...", flush=True)
    
    current_groups = {}
    current_host = None
    
    with open(OUTPUT_TS, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ",#genre#" in line:
                current_host = line.split(",")[0].strip()
                if current_host not in current_groups:
                    current_groups[current_host] = set()
            elif current_host and "," in line:
                parts = line.split(",", 1)
                current_groups[current_host].add((fix_mojibake(parts[0]), parts[1].strip()))

    hosts_to_check = list(current_groups.keys())
    print(f"📡 TS类待探测验证的 IP 组共计: {len(hosts_to_check)} 个", flush=True)

    total_new_found = 0
    success_ip_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(fetch_json_channels, host): host for host in hosts_to_check}
        for future in concurrent.futures.as_completed(futures):
            host, remote_channels = future.result()
            if not remote_channels:
                continue
            
            if host not in current_groups:
                current_groups[host] = set()

            existing_paths = {urlparse(url).path for _, url in current_groups[host]}
            
            ip_added = 0
            for ch in remote_channels:
                c_name = fix_mojibake(ch["name"])
                c_url = ch["url"]
                c_path = urlparse(c_url).path + (f"?{urlparse(c_url).query}" if urlparse(c_url).query else "")
                
                if c_path not in existing_paths:
                    full_url = f"http://{host}{c_path}"
                    current_groups[host].add((c_name, full_url))
                    existing_paths.add(c_path)
                    ip_added += 1

            if ip_added > 0:
                success_ip_count += 1
                total_new_found += ip_added
                print(f"   🎯 [TS破解成功] IP: {host} -> 成功连通并扩充了 {ip_added} 个新频道", flush=True)

    print(f"✨ TS类探测补全完毕！共成功破解 {success_ip_count} 个 IP，累计补全 {total_new_found} 条高清直播源。", flush=True)

    with open(OUTPUT_TS, "w", encoding="utf-8") as f:
        f.write("# ==========================================\n")
        f.write("# 📺 TS类直播源聚合总表 (含API智能补全与中文纠错)\n")
        f.write("# ==========================================\n\n")
        
        for host, ch_set in current_groups.items():
            f.write(f"{host},#genre#\n")
            chs_list = [{"name": item[0], "url": item[1], "path": urlparse(item[1]).path} for item in ch_set]
            sorted_chs = sorted(chs_list, key=get_channel_sort_key)
            
            seen_paths = set()
            for c in sorted_chs:
                if c['path'] not in seen_paths:
                    seen_paths.add(c['path'])
                    f.write(f"{c['name']},{c['url']}\n")
            f.write("\n")

def enhance_output_hls_from_interface():
    if not os.path.exists(OUTPUT_HLS):
        return

    print(f"\n🔍 【HLS类智能探测与补全】开始对 output_hls.txt 中的 IP 列表进行 ZHGXTV 接口探测与补全...", flush=True)
    
    current_groups = {}
    current_host = None
    
    with open(OUTPUT_HLS, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ",#genre#" in line:
                current_host = line.split(",")[0].strip()
                if current_host not in current_groups:
                    current_groups[current_host] = set()
            elif current_host and "," in line:
                parts = line.split(",", 1)
                current_groups[current_host].add((fix_mojibake(parts[0]), parts[1].strip()))

    hosts_to_check = list(current_groups.keys())
    print(f"📡 HLS类待探测验证的 IP 组共计: {len(hosts_to_check)} 个", flush=True)

    total_new_found = 0
    success_ip_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(fetch_zhgxtv_channels, host): host for host in hosts_to_check}
        for future in concurrent.futures.as_completed(futures):
            host, remote_channels = future.result()
            if not remote_channels:
                continue
            
            if host not in current_groups:
                current_groups[host] = set()

            existing_paths = {urlparse(url).path for _, url in current_groups[host]}
            
            ip_added = 0
            for ch in remote_channels:
                c_name = fix_mojibake(ch["name"])
                c_url = ch["url"]
                c_path = urlparse(c_url).path + (f"?{urlparse(c_url).query}" if urlparse(c_url).query else "")
                
                if c_path not in existing_paths:
                    current_groups[host].add((c_name, c_url))
                    existing_paths.add(c_path)
                    ip_added += 1

            if ip_added > 0:
                success_ip_count += 1
                total_new_found += ip_added
                print(f"   🎯 [HLS破解成功] IP: {host} -> 成功连通并扩充了 {ip_added} 个新频道", flush=True)

    print(f"✨ HLS类探测补全完毕！共成功破解 {success_ip_count} 个 IP，通过 ZHGXTV 接口累计补全 {total_new_found} 条高质直播源。", flush=True)

    with open(OUTPUT_HLS, "w", encoding="utf-8") as f:
        f.write("# ==========================================\n")
        f.write("# 📺 HLS类直播源聚合总表 (含ZHGXTV接口智能补全与中文纠错)\n")
        f.write("# ==========================================\n\n")
        
        for host, ch_set in current_groups.items():
            f.write(f"{host},#genre#\n")
            chs_list = [{"name": item[0], "url": item[1], "path": urlparse(item[1]).path} for item in ch_set]
            sorted_chs = sorted(chs_list, key=get_channel_sort_key)
            
            seen_paths = set()
            for c in sorted_chs:
                if c['path'] not in seen_paths:
                    seen_paths.add(c['path'])
                    f.write(f"{c['name']},{c['url']}\n")
            f.write("\n")

def run_processor():
    print(f"==================================================", flush=True)
    print(f"🚀 开始执行直播源智能分类、清理与IP聚合任务", flush=True)
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
                sorted_chs = sorted(chs, key=get_channel_sort_key)
                seen_paths = set()
                for c in sorted_chs:
                    if c['path'] not in seen_paths:
                        seen_paths.add(c['path'])
                        f.write(f"{c['name']},http://{host}{c['path']}\n")
                f.write("\n")

    write_grouped_file(OUTPUT_HLS, hls_groups, "HLS类直播源")
    write_grouped_file(OUTPUT_TS, ts_groups, "TS类直播源")
    write_grouped_file(OUTPUT_NEWLIVE, newlive_groups, "NewLive类直播源")

    enhance_output_ts_from_json()
    enhance_output_hls_from_interface()

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
