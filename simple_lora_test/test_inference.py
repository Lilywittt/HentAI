from llamafactory.chat import ChatModel
import os

def test():
    model_path = "/root/local-nvme/train_env/models/Qwen3-14B-abliterated"
    adapter_path = "/root/local-nvme/train_output/hentai_lora_results_lora_dataset_叶灵静_merged_v1.2_2026-01-25-21-42-36"
    
    print(f"Initializing model with adapter: {adapter_path}")
    chat_model = ChatModel(dict(
        model_name_or_path=model_path,
        adapter_name_or_path=adapter_path,
        template="qwen3",
        finetuning_type="lora",
        quantization_bit=4,
    ))

    messages = [{"role": "user", "content": "你好，请问你是谁？"}]
    print("\nUser: 你好，请问你是谁？")
    print("Assistant: ", end="", flush=True)
    
    response = ""
    for new_text in chat_model.stream_chat(messages):
        print(new_text, end="", flush=True)
        response += new_text
    
    print("\n\nTest Finished.")

if __name__ == "__main__":
    test()
