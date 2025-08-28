import re
import requests
import json
import time
import os
import uuid
from wxauto import WeChat

COZE_BASE_URL = "https://api.coze.cn/v3"
COZE_TOKEN = "pat_xxxx" # 你的token
COZE_BOT_ID = "xxxxx" # 你bot的id
USER_ID = "123"  # 固定用户ID
GROUP_NAME = "xxx"  # 要监听的微信群名称
POLL_INTERVAL = 0.5
MAX_POLL_ATTEMPTS = 60

# 打印函数Print JSON
def log_json(title, data, is_error=False):
    log_type = "ERROR" if is_error else "INFO"
    print("-" * 50)
    print("." * 50)
    print(f"\n[{log_type}] {title}:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("." * 50)
    print("-" * 50)

# 问答Coze Response
def coze_chat(query: str) -> str:
    url = COZE_BASE_URL
    headers = {
        "Authorization": f"Bearer {COZE_TOKEN}",
        "Content-Type": "application/json"
    }
    body = {
        "bot_id": COZE_BOT_ID,
        "user_id": USER_ID,
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {"role": "user", "content": query}
        ]
    }

    resp = requests.post(f"{url}/chat", headers=headers, json=body, timeout=10).json()
    data = resp.get("data", {})
    conversation_id = data.get("conversation_id")
    chat_id = data.get("id")

    if not conversation_id or not chat_id:
        return "[创建失败：缺少 conversation_id 或 chat_id]"

    # 轮询 Polling until completed
    retrieve_url = f"{url}/chat/retrieve"
    for _ in range(30):
        status_resp = requests.get(
            retrieve_url,
            headers=headers,
            params={"conversation_id": conversation_id, "chat_id": chat_id},
            timeout=10
        ).json()
        if status_resp.get("data", {}).get("status") == "completed":
            break
        time.sleep(0.5)

    # 取回答 
    message_url = f"{url}/chat/message/list"
    msg_resp = requests.get(
        message_url,
        headers=headers,
        params={"conversation_id": conversation_id, "chat_id": chat_id},
        timeout=10
    ).json()

    for msg in msg_resp.get("data", []):
        if msg.get("role") == "assistant" and msg.get("type") == "answer":
            return msg.get("content", "").strip()

    return "[AI无回复/超时/类型不匹配]"

# 微信消息回调
def on_msg(msg, chat):
    if not str(msg.content).startswith("/"): # 识别以/开头的消息
        return
    question = str(msg.content)[1:].strip()

    print("-" * 50)
    print("." * 50)
    print(f"[检测请求] 提取的问题: {repr(question)}")
    start_time = time.time()
    answer = coze_chat(question)
    elapsed_time = time.time() - start_time
    print(f"[处理完成] 耗时: {elapsed_time:.2f}秒")
    print(f"[处理完成] 回答: {repr(answer)}")

    # 提取图片URL
    url_match = re.search(r'https?://[^\s]+', answer)
    img_url = url_match.group(0) if url_match else None

    if img_url:
        # 下载发送图片
        try:
            r = requests.get(img_url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
            r.raise_for_status()
            img_path = os.path.join("tempPhotos", f"{uuid.uuid4().hex}.jpg")
            with open(img_path, "wb") as f:
                f.write(r.content)
            print(f"[图片下载] 已保存到 {img_path}")
            chat.SendFiles(img_path)
            print("[发送成功] 已发送图片")
            print("." * 50)
            print("-" * 50)
            return
        except Exception as e:
            print(f"[图片处理失败] {e}")

    # 无URL/下载失败 按普通文本回复
    reply = f"@{msg.sender} {answer}"
    try:
        chat.SendMsg(reply)
        print(f"[回复成功] 内容: {repr(reply)}")
        print("." * 50)
        print("-" * 50)
    except Exception as e:
        print(f"[回复失败] 回复消息失败: {e}")
        print("." * 50)
        print("-" * 50)

def main():
    os.makedirs("tempPhotos", exist_ok=True)
    group_name = GROUP_NAME
    wx = WeChat()
    log_json(
        title="监听准备",
        data={
            "目标群名": group_name,
            "检查项": [
                "1.微信窗口在桌面可见",
                "2.看到提示后再开始使用"
            ]
        },
        is_error=False
    )
    
    try:
        wx.AddListenChat(group_name, on_msg)
        print("开始监听，按 Ctrl+C 退出...\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n已停止监听。")
    except Exception as e:
        error_msg = f"监听异常: {e}"
        print(f"\n{error_msg}")
        log_json("主程序异常", {"error": str(e)}, is_error=True)

if __name__ == "__main__":
    main()