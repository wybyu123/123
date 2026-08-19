import os
import csv
import requests
import json
import datetime

# 配置文件夹
output_dir = "downloads"
special_dir = "special_files"
os.makedirs(output_dir, exist_ok=True)
os.makedirs(special_dir, exist_ok=True)

def is_m3u(content):
    return "#EXTM3U" in content or "#EXTINF" in content

def is_txt_tv_list(content):
    # 检查是否包含特殊标识或典型的 "名称,地址" 结构
    return "#genre#" in content or (',' in content and 'http' in content)

def run_scraper(csv_file):
    if not os.path.exists(csv_file):
        print(f"❌ 错误: 找不到文件 {csv_file}")
        return

    date_str = datetime.datetime.now().strftime("%m%d")
    m3u_count = 1
    txt_count = 1
    
    # 初始化 JSON 结构
    json_output = {"lives": []}
    
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None) # 跳过表头
        
        for index, row in enumerate(reader):
            if not row: continue
            host_val = row[0].strip()
            url = host_val if host_val.startswith("http") else f"http://{host_val}"
            
            print(f"🔗 正在处理: {url}")
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(url, headers=headers, timeout=8)
                
                if response.status_code == 200:
                    content = response.text
                    is_m3u_file = is_m3u(content)
                    is_txt_file = is_txt_tv_list(content)
                    
                    # 判断是否为我们要的直播源文件
                    if is_m3u_file or is_txt_file:
                        ext = ".m3u" if is_m3u_file else ".txt"
                        count = m3u_count if is_m3u_file else txt_count
                        file_name = f"{date_str}h{count:02d}{ext}"
                        file_path = os.path.join(special_dir, file_name)
                        
                        with open(file_path, "w", encoding="utf-8") as out:
                            out.write(content)
                        
                        # 添加到 JSON 列表
                        json_output["lives"].append({
                            "type": 0,
                            "epg": "http://epg.52sw.top:668/?ch={name}&date={date}",
                            "logo": "https://gongdian.top/tv/taibiao/{name}.png",
                            "playerType": 2,
                            "timeout": 10,
                            "name": f"源_{date_str}h{count:02d}",
                            "url": file_path 
                        })
                        
                        if is_m3u_file: m3u_count += 1
                        else: txt_count += 1
                        print(f"✅ 已存入 special_files: {file_name}")
                    else:
                        # 非直播源文件存入 downloads
                        save_path = os.path.join(output_dir, f"other_{index}.txt")
                        with open(save_path, "w", encoding="utf-8", errors="ignore") as out:
                            out.write(content)
                            
            except Exception as e:
                print(f"⚠️ 访问失败: {e}")

    # 保存 JSON 文件
    with open("lives_output.json", "w", encoding="utf-8") as jf:
        json.dump(json_output, jf, indent=2, ensure_ascii=False)
    print("\n✨ 全部处理完毕，JSON 已生成。")

# 调用示例
# run_scraper("202608100451.csv")
