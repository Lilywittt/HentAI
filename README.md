# 隐杀 (Yin Sha) Novel Splitter

这个项目包含一个 Python 脚本，用于将《隐杀》的长篇 TXT 文件按卷和章节进行拆分，并解决原始文件的编码问题。

## 功能特点

1.  **编码转换**：将原始的 GBK 编码文本转换为现代通用的 UTF-8 编码。
2.  **分卷存储**：自动识别“第X卷”并创建对应的文件夹，将属于该卷的章节存入其中。
3.  **外篇处理**：专门处理小说末尾的“--外篇--”及“外篇 第X节”内容，将其归入独立的 `Outer_Chapters` 文件夹。
4.  **智能命名**：章节文件以 `三位数字_章节名.txt` 格式命名，保持良好的排序和可读性。
5.  **VS Code 优化**：包含针对 VS Code 的工作区设置，确保原始文件也能正常预览。

## 目录结构

*   `novel_data/original_data/`：存放原始的 `隐杀.txt`。
*   `novel_data/split_data/`：脚本生成的拆分后的文件夹结构。
*   `split_novel.py`：主要的处理脚本。
*   `.vscode/settings.json`：工作区配置文件。

## 如何运行

确保你已经安装了 Python 环境，然后在项目根目录下运行：

```bash
python split_novel.py
```

脚本会自动在 `novel_data/original_data/` 寻找 txt 文件，并将结果输出到 `novel_data/split_data/`。

## 主角语料清洗与 LoRA 数据准备

项目新增了 `clean_novel_data.py` 脚本，利用 DeepSeek API 对拆分后的章节进行深度清洗，提取结构化的交互数据。

### 功能说明
1.  **主角聚焦提取**：自动识别主角“顾家明”相关的场景，剔除无关的求票、广告及配角独角戏。
2.  **多线程并发**：支持多线程（默认 5 线程）并发调用 API，处理全本小说仅需几分钟。
3.  **结构化输出 (JSON)**：输出包含场景背景、外部触发事件、角色台词、动作描写、心理推演及情绪标签的 JSON 数据。
4.  **可视化监控**：实时进度条（tqdm）+ 持久化日志系统。

### 如何运行清洗任务
1.  **安装依赖**：
    ```bash
    pip install openai python-dotenv tqdm
    ```
2.  **配置 API Key**：
    将 `.env.example` 复制为 `.env`，填入你的 `DEEPSEEK_API_KEY`。
3.  **执行清洗**：
    ```bash
    python clean_novel_data.py
    ```

### 清洗接口说明
您可以修改 `clean_novel_data.py` 最后的 `run_cleaning_task` 调用参数：
*   清洗特定卷：`run_cleaning_task(volume_prefix="02")`
*   清洗全本：`run_cleaning_task(volume_prefix=None)`

## 技术实现细节

*   **正则分割**：脚本使用 Unicode 转义（如 `\u7b2c` 代表 `第`）来编写正则表达式，从而避免在某些系统环境下 Python 脚本自身的编码冲突。
*   **状态保持**：在遍历拆分后的片段时，脚本会跟踪当前的卷名，并根据匹配到的卷标志动态更新目标存储文件夹。
*   **文件名清洗**：自动剔除非法的 Windows 文件名字符，同时保留中文字符以增强可读性。
