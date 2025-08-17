# main.py (最终完美版 - v4)
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

# --- 升级版功能：获取飞书 tenant_access_token (带错误处理) ---
def get_feishu_token():
    if feishu_token_cache["token"] and feishu_token_cache["expire_at"] > time.time():
        return feishu_token_cache["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == 0:
            feishu_token_cache["token"] = data["tenant_access_token"]
            feishu_token_cache["expire_at"] = time.time() + data.get("expire", 7200) - 300
            print("成功获取并缓存了新的飞书 token")
            return feishu_token_cache["token"]
        else:
            print(f"获取飞书 token 失败，飞书返回: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"请求飞书 token 接口时网络失败: {e}")
        return None

# --- 升级版功能：根据 open_id 获取用户名 ---
def get_user_name(user_id):
    token = get_feishu_token()
    if not token:
        return user_id 

    # *** 核心修改点 1: 在URL中明确指定我们提供的ID类型是 open_id ***
    url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id}?user_id_type=open_id"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("user", {}).get("name", user_id)
    except requests.exceptions.RequestException as e:
        print(f"获取用户名失败: {e}")
        return user_id

# --- 飞书事件的主处理函数 ---
@app.route('/feishu-event', methods=['POST'])
def handle_feishu_event():
    data = request.json
    
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data.get('challenge')})

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
        
        # *** 核心修改点 2: 明确从 sender_id 中获取 open_id ***
        user_id = sender_info.get('sender_id', {}).get('open_id')
        
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

# 默认路由，用于 UptimeRobot 唤醒服务 (保持不变)
@app.route('/', methods=['GET'])
def keep_alive():
    return "Service is alive.", 200
