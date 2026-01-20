# LoRA 训练最简流程方案

## 1. 目录结构
- `configs/`: 存放训练配置文件 (YAML)，定义模型路径、训练方法、超参数等。
- `data/`: 存放数据软链接及动态生成的 `dataset_info.json`。
- `run_lora_test.sh`: 统一启动脚本，封装了环境激活、数据挂载和训练逻辑。
- `../novel_data/lora_train_output/`: **(推荐位置)** 训练结果保存目录，与数据同级便于管理。

## 2. 数据流 (Data Flow)
1. **指定源数据**: 用户执行脚本并传入外部 `.jsonl` 文件路径。
2. **创建软链接**: 脚本在 `./data/` 下建立指向源文件的符号链接（实现零复制接入）。
3. **动态注册**: 脚本自动更新 `./data/dataset_info.json`，将新数据注册为 `dynamic_dataset`。
4. **加载配置**: LLaMA-Factory 读取 `./configs/lora_sft.yaml` 中定义的模型与训练参数。
5. **执行训练**: 启动微调，产出 Adapter 权重并保存至输出目录。

## 3. 快速开始

### 命令行模式 (CLI)
```bash
# 启动训练
./run_lora_test.sh <数据文件路径.jsonl>
```

### 可视化模式 (WebUI)
如果您希望通过网页端进行点选操作，请在终端执行：
```bash
cd /root/workspace/HentAI/simple_lora_test
./run_webui.sh
```
启动后，在浏览器访问 `http://localhost:7860`。在“数据集”选项中，您将能直接看到通过脚本动态注册的数据。

## 4. 参数微调
所有训练参数均在 `configs/lora_sft.yaml` 中管理，常用项说明：
- `learning_rate`: 学习率，默认为 `1e-4`。
- `num_train_epochs`: 训练轮数，默认为 `3.0`。
- `cutoff_len`: 最大文本长度，默认为 `2048`。
- `lora_target`: LoRA 挂载模块，`all` 表示覆盖所有线性层（效果最佳）。
- `output_dir`: 训练结果保存路径，已预设在 `novel_data` 下。
