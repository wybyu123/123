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

def parse_txt_or_m3u(file_path):
    """
    解析 downloads 文件夹下的 txt 或 m3u 文件，
    提取出所有的频道名称和对应的完整 URL。
    """
    channels = []
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
            # 尝试通过逗号或空格分割
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url})
            else:
                # 如果没有逗号，试着用空白字符分割
                parts = line.split()
                if len(parts) >= 2 and parts[-1].startswith("http"):
                    name = " ".join(parts[:-1]).strip()
                    url = parts[-1].strip()
                    channels.append({"name": name, "url": url})
    except Exception as e:
        print(f"⚠️ 解析文件出错 {file_path}: {e}", flush=True)
    
    return channels

def run_processor():
    print(f"📂 正在扫描 downloads 文件夹: {DOWNLOADS_DIR}", flush=True)
    if not os.path.exists(DOWNLOADS_DIR):
        print(f"❌ 致命错误: 找不到目标目录 {DOWNLOADS_DIR}", flush=True)
        sys.exit(1)

    # 1. 区分并筛选出所有的 txt 和 m3u 文件
    target_files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) 
                    if f.lower().endswith((".txt", ".m3u"))]
    print(f"📊 共发现 {len(target_files)} 个源文件，开始提取与分类...", flush=True)

    # 三大类链接的归类字典：以 host (IP:Port) 为 Key，存放其包含的频道列表
    hls_groups = {}     # 对应 /hls/501/index.m3u8
    ts_groups = {}      # 对应 /tsfile/live/0001_1.m3u8...
    newlive_groups = {} # 对应 /newlive/live/hls/2/live.m3u8
    
    # 记录所有涉及的 IP+端口 集合（用于生成第四个大文件）
    all_ip_ports_set = set()

    total_links_found = 0

    # 2. 遍历所有文件提取链接并归类
    for file_path in target_files:
        channels = parse_txt_or_m3u(file_path)
        for ch in channels:
            url = ch["name"] and ch["url"] and ch["url"] or (ch["url"] if isinstance(ch, dict) else "")
            # 兼容处理
            name = ch.get("name", "未知频道")
            url = ch.get("url", "")
            if not url:
                continue

            total_links_found += 1
            parsed_url = urlparse(url)
            host = parsed_url.netloc  # 获取 IP:Port
            path = parsed_url.path + (f"?{parsed_url.query}" if parsed_url.query else "")

            if not host:
                continue

            # 区分三种目标后缀特征
            if "/hls/" in path and path.endswith("index.m3u8"):
                if host not in hls_groups:
                    hls_groups[host] = []
                hls_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)

            elif "/tsfile/live/" in path:
                if host not in ts_groups:
                    ts_groups[host] = []
                ts_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)

            elif "/newlive/live/hls/" in path:
                if host not in newlive_groups:
                    newlive_groups[host] = []
                newlive_groups[host].append({"name": name, "path": path})
                all_ip_ports_set.add(host)

    print(f"🔍 检索完成！共扫描处理有效链接条目: {total_links_found} 条", flush=True)
    print(f"📌 分类统计 -> 类型一(HLS): {len(hls_groups)} 个IP | 类型二(TS): {len(ts_groups)} 个IP | 类型三(NewLive): {len(newlive_groups)} 个IP", flush=True)

    # 3. 写入前三种分类大文件（按 IP 分组合并）
    def write_grouped_file(filepath, groups_dict, title_tag):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# ==========================================\n")
            f.write(f"# 📺 {title_tag} 直播源聚合总表\n")
            f.write(f"# ==========================================\n\n")
            for host, chs in groups_dict.items():
                f.write(f"{host},#genre#\n")
                # 去重当前 IP 下同名或同路径的频道
                seen_paths = set()
                for c in chs:
                    if c['path'] not in seen_paths:
                        seen_paths.add(c['path'])
                        f.write(f"{c['name']},http://{host}{c['path']}\n")
                f.write("\n")

    write_grouped_file(OUTPUT_HLS, hls_groups, "HLS类直播源")
    write_grouped_file(OUTPUT_TS, ts_groups, "TS类直播源")
    write_grouped_file(OUTPUT_NEWLIVE, newlive_groups, "NewLive类直播源")

    # 4. 生成第四个文件：将包含这三大类特征的所有 IP+端口 汇总生成大文件
    with open(OUTPUT_ALL_IP, "w", encoding="utf-8") as f:
        f.write("# ==========================================\n")
        f.write("# 🌐 命中目标特征的全部 IP+端口 汇总清单\n")
        f.write("# ==========================================\n\n")
        for ip_port in sorted(list(all_ip_ports_set)):
            f.write(f"{ip_port}\n")

    print(f"\n✅ 所有文件合并处理完毕！", flush=True)
    print(f"📁 1. HLS总表已生成: {OUTPUT_HLS}", flush=True)
    print(f"📁 2. TS总表已生成: {OUTPUT_TS}", flush=True)
    print(f"📁 3. NewLive总表已生成: {OUTPUT_NEWLIVE}", flush=True)
    print(f"📁 4. 纯IP+端口汇总表已生成: {OUTPUT_ALL_IP}", flush=True)

if __name__ == "__main__":
    run_processor()
