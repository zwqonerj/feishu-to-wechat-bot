# main.py
import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- 配置将从 Vercel 的环境变量中读取 ---
WECOM_BOT_WEBHOOK_URL = os.environ.get("WECOM_BOT_WEBHOOK_URL")

# 这是飞书事件订阅里一个可选的加密密钥，可以增强安全性
# 我们暂时不设置，但代码里保留这个逻辑
FEISHU_ENCRYPT_KEY = os.environ.get("FEISHU_ENCRYPT_KEY")

# 这是飞书事件订阅里的 Verification Token，用于验证请求来源
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN")

# 飞书事件的主处理函数
@app.route('/feishu-event', methods=['POST'])
def handle_feishu_event():
    if not WECOM_BOT_WEBHOOK_URL:
        print("错误：环境变量 WECOM_BOT_WEBHOOK_URL 未设置！")
        return jsonify({"error": "服务器配置缺失"}), 500

    data = request.json
    
    # 1. 处理飞书首次配置的 URL 验证
    if data.get('type') == 'url_verification':
        print("收到 URL 验证请求")
        return jsonify({'challenge': data.get('challenge')})

    # 2. 安全性校验：检查 Token 是否匹配
    header = data.get('header', {})
    if FEISHU_VERIFICATION_TOKEN and header.get('token') != FEISHU_VERIFICATION_TOKEN:
        print("错误：Verification Token 不匹配！")
        return jsonify({"error": "无效的 token"}), 403

    # 3. 处理真实的消息事件
    if header.get('event_type') == 'im.message.receive_v1':
        print("收到一条新消息事件")
        try:
            event = data.get('event', {})
            message = event.get('message', {})
            
            # 我们只转发文本消息，忽略图片、文件等
            if message.get('message_type') != 'text':
                return jsonify({'status': '忽略非文本消息'})

            content_data = json.loads(message.get('content', '{}'))
            text_content = content_data.get('text', '').strip()
            
            if not text_content:
                return jsonify({'status': '忽略空消息'})

            # 获取发送者信息 (为简化，我们暂时只用ID，后续可扩展为查询真实姓名)
            sender_info = event.get('sender', {})
            user_id = sender_info.get('sender_id', {}).get('user_id', '未知用户')
            
            # 格式化消息内容
            formatted_message = f"【飞书消息】\n发送人: {user_id}\n内容: {text_content}"
            
            # 将格式化后的消息发送到企业微信
            send_to_wecom(formatted_message)
            return jsonify({'status': '转发成功'})
        except Exception as e:
            print(f"处理消息时发生错误: {e}")
            return jsonify({'status': '处理事件时出错'}), 500

    return jsonify({'status': '未处理的事件类型'})

# 发送消息到企业微信的函数
def send_to_wecom(text_content):
    headers = {'Content-Type': 'application/json'}
    payload = { "msgtype": "text", "text": { "content": text_content } }
    try:
        response = requests.post(WECOM_BOT_WEBHOOK_URL, headers=headers, data=json.dumps(payload), timeout=5)
        response.raise_for_status() # 如果请求失败则抛出异常
        print("成功发送消息到企业微信")
    except requests.exceptions.RequestException as e:
        print(f"发送到企业微信失败: {e}")

# Vercel 会自动处理应用的启动，所以下面的 main 函数部分不是必需的，但保留也无妨
if __name__ == '__main__':
    app.run(debug=True, port=8000)
  
