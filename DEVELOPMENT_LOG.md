# 项目开发日志 (Development Log)

本文档记录 `HentAI` 项目的开发要点、技术实现与关键问题。

## 记录列表

### [2026/01/16] 小说数据结构化清洗模块
开发了小说数据清洗脚本，调用 DeepSeek API 提取指定角色的交互行为，生成中间态的结构化 JSON 数据。

- **功能**: 提取指定角色的交互行为与潜台词，将非结构化文本转化为结构化语料。
- **数据流 (Data Flow)**:
  1. **输入**: 读取 `novel_data/split_data` 下的分章文本文件。
  2. **处理**: 筛选包含目标角色的章节，构造 Prompt 调用 DeepSeek API 进行语义提取。
  3. **输出**: API 返回包含交互与潜台词的中间态 JSON 数据，写入 `novel_data/lora_dataset` 下的对应目录。
- **技术实现 (Implementation)**:
  - **异步并发**: 使用 `asyncio` + `Semaphore` 控制并发请求数，结合 `tqdm` 展示进度。
  - **成本优化**: 对文本内容计算 MD5 哈希，优先读取 `novel_data/.cache` 中的历史结果，无命中时才发起 API 请求。
  - **鲁棒性设计**: 集成 `tenacity` 库进行 API 失败重试，并强制 `response_format={"type": "json_object"}` 保证输出格式。

### [2026/01/16] 架构优化：提示词模板分离与数据校验

为了提升 Prompt 的可维护性并确保数据结构符合预期，对系统进行了重构。

- **模板分离**: 将提示词拆分为 `prompt_instruction.txt` (指令逻辑) 和 `output_schema.txt` (输出结构)。
  - `clean_novel_data.py` 在运行时动态读取两份文件并拼接，允许用户独立微调输出结构。
- **数据校验**: 新增 `validate_data.py` 脚本。
  - 使用 `Pydantic` 定义数据模型 (Model)，确保 Python 校验逻辑与 `output_schema.txt` 描述的结构一致。
  - 能够批量扫描 `novel_data/lora_dataset` 下的 JSON 文件并报告格式错误或 Schema 不匹配。
- **流程编排**: 新增 `run_pipeline.py`，串联“生成 -> 校验”全流程。

#### 修改方案归档 (From PROPOSAL.md)

**1. 文件结构变更**
- `prompt_instruction.txt`: 包含 `{output_schema}` 占位符。
- `output_schema.txt`: 仅包含 TypeScript Interface 定义。

**2. 校验脚本逻辑**
利用 Pydantic 的 `model_validate` 方法对加载的 JSON 进行强校验。

```python
class AnalysisOutput(BaseModel):
    meta_info: MetaInfo
    interaction_units: List[InteractionUnit]
```

**3. 清洗脚本适配**
`PromptManager` 新增 `load_composed_prompt` 方法，支持拼接指令与 Schema。

### [2026/01/16] 编码规范说明 (Encoding Standards)

在 Windows 环境下开发时遇到文件名和控制台输出的乱码问题（`OSError: [WinError 123]` 及 `???` 显示）。

- **解决方案**: 
  - 所有 Python 脚本必须显式声明 `# -*- coding: utf-8 -*-`。
  - **强制规范**: 项目文件统一使用 UTF-8 编码。
  - **IDE 设置**: 如果 VS Code 默认编码不是 UTF-8，请在底部状态栏手动点击编码格式并选择 "Save with Encoding" -> "UTF-8"。
  - 尽量避免在代码中硬编码非 ASCII 字符的文件名路径，或确保运行环境支持 UTF-8 路径。

### [2026/01/16] 自动化数据处理流程系统化 (Pipeline System)

整合并优化了从原始文本到结构化语料的全流程处理系统，确保数据生产的效率与质量。

- **核心流程编排 (`run_pipeline.py`)**:
  - 作为系统主入口，串联执行数据清洗与数据校验两个阶段。
  - 支持配置目标卷册范围、角色名称及强制刷新策略，实现一键式自动化运行。

- **数据清洗与生成 (`clean_novel_data.py`)**:
  - **异步架构**: 采用 `asyncio` 实现高并发 API 请求，大幅提升处理速度。
  - **智能缓存**: 基于文件内容与 Prompt 的联合哈希值生成缓存，支持增量更新，避免重复计费。
  - **格式兼容**: 生成的文件统一以 `.txt` 扩展名保存，但内容为严格的 JSON 结构，便于后续处理与人类审阅。

- **数据校验增强 (`validate_data.py`)**:
  - **强类型校验**: 基于 `Pydantic` 严格校验数据结构、字段完整性及枚举值约束（如场景类型、触发器类型）。
  - **格式自适应**: 扩展了文件扫描逻辑，同时支持校验 `.json` 及包含 JSON 内容的 `.txt` 文件，适配清洗脚本的输出格式。

### [2026/01/16] 工程化重构：配置统一与目录整理

针对项目文件日益增多的情况，进行了工程化目录整理与基础设施优化。

- **目录结构优化**:
  - 创建 `prompts/` 目录，将 `output_schema.txt`, `prompt_instruction.txt` 等模板文件移入其中，净化项目根目录。
  - 创建 `logs/` 目录，用于存放运行时产生的日志文件。

- **日志系统升级**:
  - 弃用 `print` 输出，全面转向 Python 标准 `logging` 模块。
  - `run_pipeline.py` 负责初始化全局日志配置（同时输出到 `logs/pipeline_timestamp.log` 和控制台）。
  - 子模块 (`clean_novel_data.py`, `validate_data.py`) 通过 `logging.getLogger(__name__)` 继承配置，确保所有操作记录均被持久化保存，便于排查问题。

- **依赖管理**:
  - 新增 `requirements.txt` 文件，明确列出项目所需的 Python 依赖库（`openai`, `pydantic`, `tenacity` 等）。

- **路径适配**:
  - 更新所有相关脚本中的文件路径引用，指向新的 `prompts/` 目录。

### [2026/01/17] 数据清洗精度提升与结构完整性优化

针对数据清洗过程中出现的角色误认及无互动章节数据缺失问题，进行了专项改进。

- **Prompt 负向约束增强**:
  - 在 `prompt_instruction.txt` 中增加了明确的拒绝指令：如果目标角色未参与实质性互动，必须返回空的 `interaction_units` 列表。
  - 明确严禁将其他角色的行为或对话错误地归属给主角，从而减少数据噪音。

- **输出结构完整性 (Zero-fill Output)**:
  - 优化了 `clean_novel_data.py` 的处理逻辑，确保即使目标角色在某些章节未出场，也会生成对应的 JSON 文件（包含空的 `interaction_units` 列表）。
  - 这保证了输出数据集在章节维度上的连续性与完整性，便于后续按顺序进行时序分析或训练。

- **自动化序号标记 (Local ID Labeling)**:
  - 引入了后处理机制：在数据提取完成后，由本地 Python 脚本自动为每个交互单元 (`interaction_unit`) 生成唯一 ID。
  - ID 格式为 `章节号_三位序号`（如 `012_001`），确保了编号的绝对准确与稳健，避免了 AI 在生成长文本时可能出现的计数偏差。

- **可观测性增强**:
  - 升级了日志系统，详细记录每个章节的处理结果状态：`本地过滤跳过`、`缓存命中:角色无互动`、`处理完毕:角色无互动` 或 `提取成功`。
