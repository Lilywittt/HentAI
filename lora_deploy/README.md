# LoRA 部署套件 (lora_deploy)

本目录用于自动化构建训练环境，并实现 HentAI 数据产物与 LLaMA-Factory 的快速接入。

---

## ?? 核心流程与数据流 (Workflow)

| 脚本 | 功能 | 数据/资源来源 (Input) | 影响位置 (Impact/Output) | 运行命令 (How to Run) |
| :--- | :--- | :--- | :--- | :--- |
| **`deploy_server.sh`** | 初始化环境与模型 | HF-Mirror, Gitee | `/root/local-nvme/train_env/` | `bash deploy_server.sh` |
| **`data_interface.py`** | 数据挂载 | `novel_data/lora_train_dataset/` | `train_env/LLaMA-Factory/data/` | `python data_interface.py` |
| **`check_env.py`** | 状态报告 | 检查 `/root/local-nvme/train_env/` | 控制台输出 | `python check_env.py` |

---

## ?? 配置详解 (Configuration)

### 1. 变量配置位置
*   **模型仓库 (`MODEL_REPO`)**: 位于 `deploy_server.sh` 脚本文件头部，修改以更换基座模型。
*   **本地磁盘 (`LOCAL_DISK`)**: 位于 `deploy_server.sh` 脚本文件头部，默认自动检测 `/root/local-nvme`。
*   **HF Token**: 下载受限模型前，需在终端执行 `export HF_TOKEN=你的Token`。

### 2. 系统影响
*   **磁盘**: 脚本会自动利用高速数据盘，避免撑爆 30GB 系统盘。
*   **缓存**: 强制重定向 `HF_HOME` 到数据盘 `.cache` 目录。
*   **软链接**: `data_interface.py` 建立 HentAI 数据到 LLaMA-Factory 的符号链接，并自动注册 `dataset_info.json`。

---

## ?? 体验与对话 (How to Chat)

> **注意**: 如果提示缺失 `bitsandbytes`，请先执行: `pip install bitsandbytes>=0.39.0`

### 方式 A: Web 交互界面
```bash
source /root/local-nvme/train_env/venv/bin/activate
cd /root/local-nvme/train_env/LLaMA-Factory
llamafactory-cli webui \
    --model_name_or_path /root/local-nvme/train_env/models/Qwen3-14B-abliterated \
    --template qwen \
    --quantization_bit 4 \
    --port 7860
```
*   **访问**: 浏览器打开 `http://localhost:7860`，进入 **Chat** 标签页。

### 方式 B: 终端命令行
```bash
source /root/local-nvme/train_env/venv/bin/activate
llamafactory-cli chat \
    --model_name_or_path /root/local-nvme/train_env/models/Qwen3-14B-abliterated \
    --template qwen \
    --quantization_bit 4
```
*   **交互指令**: 输入 `clear` 清理对话历史释放显存；输入 `exit` 退出对话并完全释放。

### 进阶：调整生成参数 (Parameters)
若觉得回复单一，可尝试调整参数：

*   **Web 界面**: 在界面中的 "Generation" / "参数" 面板中调整 `Temperature` (温度) 和 `Top P`。
*   **命令行**: 增加启动参数，例如：
    ```bash
    llamafactory-cli chat \
        --model_name_or_path /root/local-nvme/train_env/models/Qwen3-14B-abliterated \
        --template qwen \
        --quantization_bit 4 \
        --temperature 0.95 \
        --top_p 0.7 \
        --repetition_penalty 1.1
    ```
    *   `--temperature`: 越高越随机 (默认 0.95)。
    *   `--repetition_penalty`: 重复惩罚，大于 1.0 可减少复读 (默认 1.0)。

### 相关路径
*   **虚拟环境**: `/root/local-nvme/train_env/venv`
*   **框架目录**: `/root/local-nvme/train_env/LLaMA-Factory`
*   **模型文件**: `/root/local-nvme/train_env/models/Qwen3-14B-abliterated`
