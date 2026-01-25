# HentAI LoRA 体验与开发指南

本文档介绍如何在并行科技严苛的网络环境下，使用现有的公网分享功能，以及如何高效地进行后续开发。

---

## 一、 现在的用法：手动启动公网 Chatbot

为了防止产生僵尸进程，目前的后台服务已全部清理。如果您想让其他人访问，请按照以下步骤**手动启动**：

### 1. 启动服务 (第一步)
打开一个终端，执行以下命令加载模型（耗时约 1-2 分钟）：
```bash
cd workspace/HentAI/simple_lora_test
VENV_DIR="/root/local-nvme/train_env/venv"
source "${VENV_DIR}/bin/activate"
python public_share_chat.py --adapter_name_or_path /root/local-nvme/train_output/hentai_lora_results_lora_dataset_叶灵静_merged_v1.2_2026-01-25-21-42-36
```
直到看到 `Running on local URL: http://0.0.0.0:7860` 提示。

### 2. 开启公网转发 (第二步)
**保持第一个终端别关**，再开一个新终端执行以下命令获取公网链接：
```bash
ssh -o StrictHostKeyChecking=no -R 80:localhost:7860 serveo.net
```
执行后，屏幕会输出一个 `https://xxxxxxxx.serveousercontent.com` 链接，直接复制发给朋友即可。

### 3. 安全信息
*   链接访问需要账号：`admin` 密码：`hentai123`。
*   **退出方法**: 在两个终端分别按下 `Ctrl+C` 即可彻底关闭，不会留下任何僵尸进程。

---

## 二、 写代码的方法：利用 VS Code 端口转发开发

如果您想基于目前的模型开发自己的前端（如 React/Vue）或调用接口，请使用此“开发模式”。

### 1. 开发流程
并行科技服务器作为 **API 算力源**，VS Code 作为 **安全隧道**。

1.  **启动 API 后端**:
    运行 `api_backend.py`，它会开启一个符合 OpenAI 标准的接口（默认端口 `8000`）。
    ```bash
    python api_backend.py --port 8000
    ```
2.  **VS Code 自动转发**:
    *   VS Code 会在右下角弹出“端口 8000 已转发”。
    *   您可以在 VS Code 的 **“端口”面板** (Ports) 看到 `8000`。
3.  **在本地写代码**:
    现在，您可以在您自己的电脑上用任何语言写代码，直接请求 `http://127.0.0.1:8000/v1`。
    
    **Python 示例**:
    ```python
    from openai import OpenAI
    client = OpenAI(api_key="none", base_url="http://127.0.0.1:8000/v1")
    
    response = client.chat.completions.create(
        model="qwen3",
        messages=[{"role": "user", "content": "你好"}]
    )
    print(response.choices[0].message.content)
    ```

### 2. 为什么这样写代码？
*   **无需公网**: 只要 VS Code 连着，您本地代码就像在服务器上运行一样。
*   **零延迟调试**: 接口响应直接回传本地，方便您直接在本地查看 UI 渲染。
*   **一键公开**: 如果您在本地写好了网页并想分享，只需在 VS Code 端口面板中，将端口的“访问权限”从 `Private` 改为 `Public`，VS Code 会为您生成一个官方的转发链接。

---

## 三、 文件清单说明
*   `public_share_chat.py`: 现在的公网 Chatbot 核心逻辑。
*   `run_public_share.sh`: 一键启动公网分享的入口。
*   `api_backend.py`: 纯 API 后端逻辑（用于写代码调用）。
*   `configs/`: 存放 LLaMA-Factory 的路径与模型配置。
