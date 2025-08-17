# main.py (最终人性化优化+完整版)
import os
import requests
import json
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 新增：用户ID别名簿 ---
# 您可以在这里手动添加已知用户的 open_id/user_id 和他们的真实姓名
USER_ID_ALIAS = {
    "b37126g7": "个人威",
    "5d5g44cg": "邹文强"
    # 格式: "飞书提供的ID": "您想显示的姓名"
}

# --- 从环境变量读取所有配置 ---
WECOM_BOT_WEBHOOK_URL = os.environ.get("WECOM_BOT_WEBHOOK_URL")
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")

# --- 飞书事件的主处理函数 ---
@app.route('/feishu-event', methods=['POST'])
def handle_feishu_event():
    data = request.json
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data.get('challenge')})
    if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
        print("收到一条新消息事件")
        event = data.get('event', {})
        sender_info = event.get('sender', {})
        sender_id_map = sender_info.get('sender_id', {})
        user_id = sender_id_map.get('user_id') or sender_id_map.get('open_id')
        
        # 策略 1: 优先从我们手动维护的“别名簿”里找名字
        sender_name = USER_ID_ALIAS.get(user_id)
        
        # 策略 2: 如果别名簿里没有，就直接使用ID，确保消息能发出
        if not sender_name:
            sender_name = user_id if user_id else "未知用户"

        message = event.get('message', {})
        if message.get('message_type') != 'text':
            return jsonify({'status': '忽略非文本消息'})
        content_data = json.loads(message.get('content', '{}'))
        text_content = content_data.get('text', '').strip()
        
        if not text_content:
            return jsonify({'status': '忽略空消息'})
            
        formatted_message = f"【飞书消息】\n发送人: {sender_name}\n内容: {text_content}"
        send_to_wecom(formatted_message)
        return jsonify({'status': '转发成功'})
    return jsonify({'status': '未处理的事件类型'})

# 发送消息到企业微信的函数
def send_to_wecom(text_content):
    headers = {'Content-Type': 'application/json'}
    payload = {"msgtype": "text", "text": {"content": text_content}}
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
