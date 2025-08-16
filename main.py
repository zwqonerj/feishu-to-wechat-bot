# main.py (升级版 - v2)
import os
import requests
import json
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 从环境变量读取所有配置 ---
WECOM_BOT_WEBHOOK_URL = os.environ.get("WECOM_BOT_WEBHOOK_URL")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")

# --- 用于缓存飞书 tenant_access_token 的全局变量 ---
feishu_token_cache = {
    "token": "",
    "expire_at": 0
}

# --- 新增功能：获取飞书 tenant_access_token ---
def get_feishu_token():
    # 如果缓存中的 token 有效，则直接返回
    if feishu_token_cache["token"] and feishu_token_cache["expire_at"] > time.time():
        return feishu_token_cache["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # 缓存新的 token 和过期时间 (提前5分钟失效以防万一)
        feishu_token_cache["token"] = data["tenant_access_token"]
        feishu_token_cache["expire_at"] = time.time() + data["expire"] - 300
        print("成功获取并缓存了新的飞书 token")
        return feishu_token_cache["token"]
    except requests.exceptions.RequestException as e:
        print(f"获取飞书 token 失败: {e}")
        return None

# --- 新增功能：根据 user_id 获取用户名 ---
def get_user_name(user_id):
    token = get_feishu_token()
    if not token:
        return user_id # 如果获取 token 失败，则返回原始 ID

    url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        # 返回用户的名字，如果获取失败则返回原始 ID
        return data.get("data", {}).get("user", {}).get("name", user_id)
    except requests.exceptions.RequestException as e:
        print(f"获取用户名失败: {e}")
        return user_id

# --- 飞书事件的主处理函数 (已修改) ---
@app.route('/feishu-event', methods=['POST'])
def handle_feishu_event():
    data = request.json
    
    # URL 验证
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data.get('challenge')})

    # 处理消息事件
    if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
        print("收到一条新消息事件")
        event = data.get('event', {})
        message = event.get('message', {})
        
        if message.get('message_type') != 'text':
            return jsonify({'status': '忽略非文本消息'})

        content_data = json.loads(message.get('content', '{}'))
        text_content = content_data.get('text', '').strip()
        
        if not text_content:
            return jsonify({'status': '忽略空消息'})

        sender_info = event.get('sender', {})
        user_id = sender_info.get('sender_id', {}).get('user_id')
        
        # *** 核心修改点：调用新函数获取用户名 ***
        if user_id:
            sender_name = get_user_name(user_id)
        else:
            sender_name = "未知用户"

        formatted_message = f"【飞书消息】\n发送人: {sender_name}\n内容: {text_content}"
        
        send_to_wecom(formatted_message)
        return jsonify({'status': '转发成功'})

    return jsonify({'status': '未处理的事件类型'})

# 发送消息到企业微信的函数 (保持不变)
def send_to_wecom(text_content):
    headers = {'Content-Type': 'application/json'}
    payload = { "msgtype": "text", "text": { "content": text_content } }
    try:
        response = requests.post(WECOM_BOT_WEBHOOK_URL, headers=headers, data=json.dumps(payload), timeout=5)
        response.raise_for_status()
        print("成功发送消息到企业微信")
    except requests.exceptions.RequestException as e:
        print(f"发送到企业微信失败: {e}")

# 默认路由，用于 UptimeRobot 唤醒服务
@app.route('/', methods=['GET'])
def keep_alive():
    return "Service is alive.", 200
