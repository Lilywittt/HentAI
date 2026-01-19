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

## ?? 运行建议
1.  **磁盘**: 确保挂载了本地数据盘，否则 Qwen-14B 等模型会下载失败。
2.  **显存**: 训练 14B 模型建议在启动参数中加入 `4-bit` 量化。
