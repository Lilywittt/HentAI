# 隐杀 (Yin Sha) Novel Splitter & Cleaner (HentAI)

An AI project that extracts the main character of a novel into structured data for LoRA training and AI agents.

## 功能特点

1.  **拆分功能 (`split_novel.py`)**：
    *   **编码转换**：将原始的 GBK 编码文本转换为现代通用的 UTF-8 编码。
    *   **智能分卷**：自动识别“第X卷”并创建对应的文件夹。
    *   **外篇处理**：专门处理外篇内容，将其归入独立文件夹。
    *   **可读性优化**：按序号排序，清洗 Windows 非法字符。

2.  **清洗提取功能 (`clean_novel_data.py`)**：
    *   **主角聚焦提取**：利用 DeepSeek API 自动提取主角“顾家明”相关的场景。
    *   **多线程并发**：支持多线程并行调用，极速处理。
    *   **交互单元结构化**：输出 JSON 格式，包含背景、触发事件、台词、心理活动推演、情绪等。
    *   **可视化监控**：实时进度条 + 静态日志双重反馈。

## 目录结构

*   `novel_data/original_data/`：存放原始小说 TXT。
*   `novel_data/split_data/`：存放拆分后的卷册。
*   `novel_data/lora_dataset/`：存放清洗后的结构化数据。

## 如何开始

### 1. 拆分原著
```bash
python split_novel.py
```

### 2. 清洗语料
1.  安装依赖：`pip install openai python-dotenv tqdm`
2.  配置 `.env`：填入你的 `DEEPSEEK_API_KEY`。
3.  运行：`python clean_novel_data.py`

## 清洗接口说明
您可以修改 `clean_novel_data.py` 最后的 `run_cleaning_task` 调用参数：
*   清洗特定卷：`run_cleaning_task(volume_prefix="02")`
*   清洗全本：`run_cleaning_task(volume_prefix=None)`

## 技术细节
脚本使用 Unicode 转义（如 `\u7b2c`）处理正则，确保在 Windows 环境下不发生编码冲突。所有 API 调用均经过异步/多线程优化，且具备完善的容错机制。
