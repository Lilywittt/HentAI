import argparse
import os
import yaml
import gradio as gr
import html
from llamafactory.chat import ChatModel

def load_config(config_path):
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def main():
    parser = argparse.ArgumentParser(description="HentAI Public Share Chat Service")
    parser.add_argument("--model_name_or_path", type=str, help="Base model path")
    parser.add_argument("--adapter_name_or_path", type=str, help="LoRA adapter path")
    parser.add_argument("--template", type=str, default="qwen3", help="Chat template")
    parser.add_argument("--username", type=str, default="admin", help="Gradio auth username")
    parser.add_argument("--password", type=str, default="hentai123", help="Gradio auth password")
    parser.add_argument("--port", type=int, default=7860, help="Gradio port")
    
    args = parser.parse_args()

    config = load_config("configs/hentai_webui_config.yaml")
    
    model_path = args.model_name_or_path or "/root/local-nvme/train_env/models/Qwen3-14B-abliterated"
    adapter_path = args.adapter_name_or_path
    if not adapter_path:
        adapter_path = config.get("train.output_dir")
        if adapter_path and not os.path.exists(os.path.join(adapter_path, "adapter_config.json")):
            adapter_path = None

    print(f"--- Loading Model ---")
    print(f"Base Model: {model_path}")
    print(f"Adapter: {adapter_path}")

    chat_model = ChatModel(dict(
        model_name_or_path=model_path,
        adapter_name_or_path=adapter_path,
        template=args.template or config.get("top.template", "qwen3"),
        finetuning_type=config.get("top.finetuning_type", "lora"),
        quantization_bit=int(config.get("top.quantization_bit", 4)),
    ))

    def bot_msg(history):
        SYSTEM_PROMPT = "你现在是叶灵静。"
        
        messages = []
        is_first = True
        for human, ai in history[:-1]:
            content = human
            if is_first:
                content = f"{SYSTEM_PROMPT}\n\n{human}"
                is_first = False
            messages.append({"role": "user", "content": content})
            if ai:
                messages.append({"role": "assistant", "content": ai})
        
        last_user_msg = history[-1][0]
        if is_first:
            last_user_msg = f"{SYSTEM_PROMPT}\n\n{last_user_msg}"
        messages.append({"role": "user", "content": last_user_msg})

        print(f"\nUser: {history[-1][0]}")
        print("Bot Thinking/Responding...", flush=True)

        history[-1][1] = ""
        try:
            for new_text in chat_model.stream_chat(messages):
                # 关键修复：强制对 HTML 敏感字符进行转义，防止标签导致的前端显示消失
                escaped_text = html.escape(new_text)
                history[-1][1] += escaped_text
                yield history
        except Exception as e:
            print(f"\nError: {e}")
            history[-1][1] = f"发生错误: {e}"
            yield history
        print("\n--- Done ---")

    def add_text(history, text):
        if not text:
            return history, ""
        return history + [[text, None]], ""

    with gr.Blocks(title="HentAI Chat (Fixed)") as demo:
        gr.Markdown("# HentAI 体验对话框 - 叶灵静")
        chatbot = gr.Chatbot(label="对话窗口 (支持特殊标签显示)", height=500)
        
        with gr.Row():
            msg = gr.Textbox(placeholder="输入消息后按回车...", scale=9)
            submit_btn = gr.Button("发送", scale=1)

        with gr.Row():
            btn1 = gr.Button("请自我介绍一下")
            btn2 = gr.Button("到我被窝里来，我们做涩涩的事")
            clear = gr.Button("清空记录")

        msg.submit(add_text, [chatbot, msg], [chatbot, msg]).then(bot_msg, chatbot, chatbot)
        submit_btn.click(add_text, [chatbot, msg], [chatbot, msg]).then(bot_msg, chatbot, chatbot)
        
        btn1.click(lambda h: h + [["请自我介绍一下", None]], chatbot, chatbot).then(bot_msg, chatbot, chatbot)
        btn2.click(lambda h: h + [["到我被窝里来，我们做涩涩的事", None]], chatbot, chatbot).then(bot_msg, chatbot, chatbot)
        clear.click(lambda: None, None, chatbot)

    print(f"--- Launching Service (v2) ---")
    demo.queue().launch(
        server_name="0.0.0.0", 
        server_port=args.port,
        auth=(args.username, args.password)
    )

if __name__ == "__main__":
    main()
