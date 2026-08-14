import os

# ---------------- 配置区域 ----------------
CSV_FILE = "202608100451.csv"         # 你的主 CSV 文件
RAW_WEB_FILE = "fofa_web_raw.txt"     # 你从 FOFA 网页复制或导出的原始文本文件
# ------------------------------------------

def get_existing_hosts(csv_path):
    """读取本地已有的 host 用于去重"""
    existing = set()
    if not os.path.exists(csv_path):
        return existing
    
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[1:]: # 跳过表头
            parts = line.strip().split(",")
            if parts and parts[0]:
                existing.add(parts[0].strip())
    return existing

def process_web_data():
    if not os.path.exists(RAW_WEB_FILE):
        print(f"⚠️ 未找到原始数据文件: {RAW_WEB_FILE}")
        print(f"💡 提示: 请把从 FOFA 网页复制的内容保存到 {RAW_WEB_FILE} 中再运行此脚本。")
        return

    print(f"📂 正在读取网页原始数据: {RAW_WEB_FILE}")
    
    # 1. 加载本地已有数据进行去重
    existing_hosts = get_existing_hosts(CSV_FILE)
    print(f"📊 本地 CSV 当前已有记录数: {len(existing_hosts)}")

    new_rows = []
    added_count = 0
    skipped_count = 0

    # 2. 逐行解析网页抓取/复制下来的文本
    with open(RAW_WEB_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # 智能清洗：有些从网页复制下来的可能带有其他杂乱字符，我们尝试提取 IP 和 端口
            # 常见格式如: 121.23.45.67:80 或带 http:// 的形式
            ip = ""
            port = "80"
            host = ""

            if line.startswith("http://") or line.startswith("https://"):
                host = line
                # 简单剥离
                clean_part = line.split("://")[1].split("/")[0]
                if ":" in clean_part:
                    ip, port = clean_part.split(":")
                else:
                    ip = clean_part
                    port = "443" if line.startswith("https") else "80"
            elif ":" in line:
                parts = line.split(":")
                ip = parts[0].strip()
                port = parts[1].strip()
                host = f"{ip}:{port}"
            else:
                # 纯 IP 的情况
                ip = line
                port = "80"
                host = ip

            # 校验 IP 格式是否合法（简单判断包含点）
            if "." not in ip:
                skipped_count += 1
                continue

            # 去重判断
            if host not in existing_hosts:
                existing_hosts.add(host)
                new_rows.append(f"{host},{ip},{port}\n")
                added_count += 1
            else:
                skipped_count += 1

    if added_count == 0:
        print("✨ 没有发现全新内容（所有数据均已存在于本地），CSV 无需更新。")
        return

    # 3. 写入文件 (若文件不存在则自动创建并写入表头)
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("host,ip,port\n")
        f.writelines(new_rows)

    print(f"🚀 导入成功！")
    print(f"   - 本次新增记录: {added_count} 条")
    print(f"   - 重复/跳过记录: {skipped_count} 条")
    print(f"   - 文件已更新至: {CSV_FILE}")

if __name__ == "__main__":
    process_web_data()
