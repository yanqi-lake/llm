import json

def extract_stage3_content(file_path):
    """
    读取JSON文件并提取stage3的文本内容
    """
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # 提取stage3的内容
        stage3_content = data.get('stage3', {}).get('response', '')
        
        if not stage3_content:
            print("警告：stage3中没有找到response内容")
            return None
        
        # 输出到终端
        print("=" * 80)
        print("stage3 内容（终端输出）：")
        print("=" * 80)
        print(stage3_content)
        print("=" * 80)
        
        # 保存到文本文件
        output_file = 'stage3_output.txt'
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(stage3_content)
        
        print(f"\n内容已成功保存到文件：{output_file}")
        
        return stage3_content
        
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"错误：文件 {file_path} 不是有效的JSON格式")
        return None
    except Exception as e:
        print(f"发生未知错误：{e}")
        return None

if __name__ == "__main__":
    # 设置JSON文件路径
    json_file = 'results.json'  # 如果文件不在同一目录，请修改路径
    
    # 执行提取和输出
    content = extract_stage3_content(json_file)
    
    if content:
        print(f"\n提取完成！内容长度：{len(content)} 字符")