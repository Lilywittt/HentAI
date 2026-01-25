import argparse
import os
import yaml
from llamafactory.chat import ChatModel
from llamafactory.extras.constants import METHODS
from llamafactory.api.app import create_app

def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def main():
    parser = argparse.ArgumentParser(description="HentAI API Backend")
    parser.add_argument("--adapter_name_or_path", type=str, help="LoRA adapter path")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    args = parser.parse_args()

    config = load_config("configs/hentai_webui_config.yaml")
    
    model_path = "/root/local-nvme/train_env/models/Qwen3-14B-abliterated"
    adapter_path = args.adapter_name_or_path or config.get("train.output_dir", "")
    template = config.get("top.template", "qwen3")

    print(f"--- Launching API Backend ---")
    print(f"Base Model: {model_path}")
    print(f"Adapter: {adapter_path}")
    
    chat_args = dict(
        model_name_or_path=model_path,
        adapter_name_or_path=adapter_path,
        template=template,
        finetuning_type="lora",
        quantization_bit=4,
    )
    
    chat_model = ChatModel(chat_args)
    app = create_app(chat_model)
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port, workers=1)

if __name__ == "__main__":
    main()
