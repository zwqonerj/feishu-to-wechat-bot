# main.py (最终优雅降级版 - v6)
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

# --- 获取飞书 tenant_access_token ---
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

# --- 最终版功能：智能判断 ID 类型并获取用户名 (带优雅降级) ---
def get_user_name(user_id_str):
    token = get_feishu_token()
    if not token or not user_id_str:
        return user_id_str 

    user_id_type = "user_id" if user_id_str.startswith("ou_") else "open_id"
    url = f"https://open.feishu.cn/open-apis/contact/v3/users/{user_id_str}?user_id_type={user_id_type}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json() # 无论成功失败都先解析返回的json
        
        # 只有当请求成功(HTTP 200)且飞书业务码为0时，才算成功
        if response.status_code == 200 and data.get("code") == 0:
            return data.get("data", {}).get("user", {}).get("name", user_id_str)
        else:
            # 任何其他情况（包括400错误），都打印日志并返回原始ID
            print(f"查询用户名失败, HTTP状态码: {response.status_code}, 飞书返回: {data}")
            # 您也可以在这里返回一个更友好的名字，比如 "外部用户"
            # return "外部用户" 
            return user_id_str
            
    except requests.exceptions.RequestException as e:
        print(f"请求获取用户名接口时网络失败: {e}")
        return user_id_str

# --- 飞书事件的主处理函数 (保持不变) ---
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
        sender_id_map = sender_info.get('sender_id', {})
        user_id = sender_id_map.get('user_id') or sender_id_map.get('open_id')
        
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

# 默认路由 (保持不变)
@app.route('/', methods=['GET'])
def keep_alive():
    return "Service is alive.", 200
