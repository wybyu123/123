import os

# ---------------- 配置区域 ----------------
TARGET_CSV = "202608100451.csv"       # 你的主总库 CSV 文件
NEW_INPUT_FILE = "fofa_web_raw.txt"   # 你从网页复制或下载保存的新数据文件
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

def import_and_merge():
    if not os.path.exists(NEW_INPUT_FILE):
        print(f"⚠️ 未找到新数据文件: {NEW_INPUT_FILE}")
        print(f"💡 提示: 请把你在 FOFA 网页复制或导出的内容保存到 {NEW_INPUT_FILE} 中。")
        return

    print(f"📂 正在读取新数据源: {NEW_INPUT_FILE}")
    
    # 1. 加载本地已有数据进行去重
    existing_hosts = get_existing_hosts(TARGET_CSV)
    print(f"📊 主库 CSV 当前记录数: {len(existing_hosts)}")

    new_rows = []
    added_count = 0
    skipped_count = 0

    # 2. 逐行解析新数据
    with open(NEW_INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("host"): # 跳过空行或可能的表头
                continue
            
            ip = ""
            port = "80"
            host = ""

            # 兼容多种格式：URL、IP:Port 或纯 IP
            if line.startswith("http://") or line.startswith("https://"):
                host = line
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
                ip = line
                port = "80"
                host = ip

            # 简单校验是否包含有效 IP 特征
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
        print("✨ 没有发现全新内容（所有数据在主库中均已存在）。")
        return

    # 3. 写入主 CSV 文件
    file_exists = os.path.exists(TARGET_CSV)
    with open(TARGET_CSV, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("host,ip,port\n")
        f.writelines(new_rows)

    print(f"🚀 导入合并成功！")
    print(f"   - 本次新增记录: {added_count} 条")
    print(f"   - 重复/跳过记录: {skipped_count} 条")
    print(f"   - 主库已更新: {TARGET_CSV}")

if __name__ == "__main__":
    import_and_merge()
