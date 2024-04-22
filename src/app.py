import os
import random
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ConfirmTemplate, MessageAction, PostbackAction
)

app = Flask(__name__)

# LINE Bot APIとWebhook Handlerの初期化
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# 室蘭工業大学の学生の晩ご飯一覧
bangohan_list = ["SAINO", "章吉", "もっちゃん", "なかよし", "学食", "夕月庵", "チャイナ", "コンビニ", "自炊"]

@app.route("/callback", methods=['POST'])
def callback():
    # リクエストヘッダーからの署名検証
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    if user_message == "晩ご飯":
        bangohan = random.choice(bangohan_list)
        confirm_template_message = TemplateSendMessage(
            alt_text='晩ご飯をレコメンドします',
            template=ConfirmTemplate(
                text=f'今日の晩ご飯は{bangohan}でどう？',
                actions=[
                    PostbackAction(label='NO', data='action=recommend'),
                    MessageAction(label='YES', text=f'今日の晩ご飯は{bangohan}で決まり！')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, confirm_template_message)
    else:
        # 他のテキストメッセージにはエコー応答
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=user_message)
        )

@handler.add(MessageEvent, postback_event=True)
def handle_postback(event):
    if event.postback.data == 'action=recommend':
        bangohan = random.choice(bangohan_list)
        confirm_template_message = TemplateSendMessage(
            alt_text='別の晩ご飯をレコメンドします',
            template=ConfirmTemplate(
                text=f'それなら{bangohan}はどう？',
                actions=[
                    PostbackAction(label='NO', data='action=recommend'),
                    MessageAction(label='YES', text=f'今日の晩ご飯は{bangohan}で決まり！')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, confirm_template_message)

if __name__ == '__main__':
    app.run(port=8080, debug=True)
