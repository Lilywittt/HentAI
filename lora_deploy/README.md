# LoRA 部署套件详解 (LoRA Deployment Suite)

本目录包含用于自动化部署训练环境和管理数据集的工具脚本。

## 1. data_interface.py 工作原理详解

`data_interface.py` 是连接 **HentAI 数据产物** 与 **LLaMA-Factory 训练框架** 的桥梁。它的设计目标是实现“无侵入式”的数据接入。

### 为什么需要这个脚本？
LLaMA-Factory 训练框架不能直接扫描目录加载数据，它要求必须在 `data/dataset_info.json` 注册表中明确登记数据集的元数据（文件路径、列映射关系等）。手动维护这个文件既繁琐又容易出错（尤其是 JSON 格式错误）。

### 核心工作流程

该脚本执行时会自动完成以下两个关键步骤：

#### 第一步：建立“软链接” (Symlink)
脚本不会复制巨大的 JSONL 数据文件，而是创建一个轻量级的**符号链接**。
*   **源文件**: `HentAI/novel_data/lora_train_dataset/xxx.jsonl`
*   **目标**: `../train_env/LLaMA-Factory/data/hentai_lora.jsonl`

这样做的好处是节省磁盘空间，且当 HentAI 重新生成数据时，只需更新链接即可，无需物理搬运文件。

#### 第二步：自动注册 (Registration)
脚本会读取 LLaMA-Factory 的 `data/dataset_info.json`，并插入或更新如下配置：

```json
"hentai_lora": {
  "file_name": "hentai_lora.jsonl",
  "columns": {
    "prompt": "instruction",  // 对应 Alpaca 格式的指令
    "query": "input",         // 对应 Alpaca 格式的输入
    "response": "output"      // 对应 Alpaca 格式的输出
  }
}
```

**结果**：完成这一步后，您就可以在 LLaMA-Factory 的启动命令或 WebUI 中直接使用 `--dataset hentai_lora` 来加载数据了。

---

## 2. 部署脚本 (deploy_server.sh)

用于一键初始化服务器环境。

*   **隔离性**: 所有重资产（框架代码、模型权重）都会被下载到 `HentAI` 项目目录**之外**的 `../train_env` 目录中，保持代码仓库的轻量化。
*   **极速部署**: 
    *   默认使用 **Gitee (码云)** 镜像克隆 LLaMA-Factory，解决 GitHub 连接问题。
    *   默认配置 **清华 PyPI 镜像** 和 **HF-Mirror**，大幅加速依赖和模型下载。
    *   自动创建 **Python 虚拟环境 (venv)**，解决系统权限问题。
*   **模型配置**: 脚本头部定义了 `MODEL_REPO` 变量，您可以随时修改它来更换下载的基座模型（如 Qwen, Llama-3, Mistral 等）。

## 3. 环境自检 (check_env.py)

在开始训练前，运行此脚本可以快速排查常见问题：
*   [x] 训练框架是否存在？
*   [x] 基座模型是否下载完整？
*   [x] 数据集是否已通过 `data_interface.py` 正确注册？
