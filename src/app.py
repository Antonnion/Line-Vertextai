import os
import config
from flask import Flask, request, abort
from linebot.v3.messaging import MessagingApi
from linebot.v3.webhook import WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    DatetimePickerAction, MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URIAction, PostbackAction, MessageAction
)
from datetime import datetime, timedelta
import calendar
from google.cloud import bigquery
from google.cloud import aiplatform as vertexai
from vertexai.language_models import CodeGenerationModel

app = Flask(__name__)

# LINE Bot APIとWebhook Handlerの初期化
line_bot_api = MessagingApi(config.token)
handler = WebhookHandler(config.secret)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        app.logger.error(f"Exception: {str(e)}")
        abort(500)
    return 'OK'

def reply_with_carousel(event):
    columns = [
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="アルバイト＆パート",
            text="下記の中から選択してください。",
            actions=[
                MessageAction(label="シフト確認", text="月日 00:00 ~ 00:00"),
                URIAction(label="View detail", uri="https://my-service-d6nkubzq2q-uc.a.run.app")
            ]
        )
    ]
    carousel_template = CarouselTemplate(columns=columns)
    template_message = TemplateSendMessage(
        alt_text='Carousel template',
        template=carousel_template
    )
    line_bot_api.reply_message(event.reply_token, template_message)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    if user_message == "おはようございます":
        reply_with_carousel(event)
    else:
        # 他のテキストメッセージに対する応答がない場合はログに記録するなどの処理を追加
        app.logger.info(f"Received message: {user_message} - No action taken.")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
