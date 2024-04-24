import os
import config
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    DatetimePickerAction, MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URIAction, PostbackAction, MessageAction
)
from datetime import datetime, timedelta
import calendar
from linebot.v3.messaging import MessagingApi
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google.cloud import bigquery
from google.cloud import aiplatform as vertexai
from vertexai.language_models import CodeGenerationModel
from vertexai.language_models import TextGenerationModel

app = Flask(__name__)

# LINE Bot APIとWebhook Handlerの初期化
line_bot_api = LineBotApi(config.token)
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
        app.logger.error(f"Exception: {str(e)}")  # 例外の詳細をログに記録
        abort(500)
    return 'OK'

def reply_with_text(user_id, user_message: str) -> str:
    vertexai.init(project="ca-sre-bpstudy1-kishimoto-dev", location="asia-northeast1")
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 1024,
        "temperature": 0.9
    }
    model = CodeGenerationModel.from_pretrained("code-bison-32k@002")
    sql_query = model.predict(
        prefix=f"You are an experienced data analyst. Write a BigQuery SQL to answer the user's prompt based on the following context:\n"
               "Create and execute the following SQL query based on the information provided by the user.\n"
               "The data to be inserted is based on the information provided by the user. \n"
               "For example, if the user provided shift information for April 12, 2022 from 10:00 am to 5:00 pm with an employee ID of 4, use the following query\n"
               "INSERT INTO `ca-sre-bpstudy1-kishimoto-dev.employee_data.kk`\n"
               "(employee_id, shiftdate, start_time, end_time)\n"
               "VALUES\n"
               "(4, '2022-04-12', '10:00:00', '17:00:00');\n"
               "---- Context ----\n"
               "Format: Plain SQL only, no Markdown\n"
               "Table: int-booster-llm-poc.kk_costoco.invent\n"
               "Restriction: None\n"
               "Schema as JSON:\n"
               "{\n"
               "    \"fields\": [\n"
               "        {\"name\": \"employee_id\", \"type\": \"INTEGER\", \"mode\": \"NULLABLE\"},\n"
               "        {\"name\": \"stock_quantity\", \"type\": \"DATE\", \"mode\": \"NULLABLE\"},\n"
               "        {\"name\": \"start_time\", \"type\": \"TIME\", \"mode\": \"NULLABLE\"}\n"
               "        {\"name\": \"end_time\", \"type\": \"TIME\", \"mode\": \"NULLABLE\"}\n"
               "    ]\n"
               "}\n\n"
               f"User's prompt: {user_id}, {user_message}",
        **parameters
    )
    client = bigquery.Client()
    query_job = client.query(sql_query)
    results = query_job.result()

def reply_with_carousel(event):
    columns = [
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="アルバイト＆パート",
            text="下記の中から選択してください。",
            actions=[
                MessageAction(label="シフト確認", text="月日 00:00 ~ 00:00"),
                MessageAction(label="アンケート開始", text="アンケートを開始します"),
                URIAction(label="View detail", uri="https://my-service-d6nkubzq2q-uc.a.run.app")
            ]
        ),
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="管理者用",
            text="下記の中から選択してください。",
            actions=[
                MessageAction(label="シフト確認", text="月日 00:00 ~ 00:00"),
                MessageAction(label="アンケート開始", text="アンケートを開始します"),
            ]
        ),
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="管理者用",
            text="下記の中から選択してください。",
            action=PostbackAction(
                    label="Buy",
                    data="action=buy&itemid=111",
                    displayText="Buy",
                    InputOption="openKeyboard",
                    FillInText="---\nName: \nPhone: \nBirthday: \n---"
                ),
        )
        
        # 追加のカラムをここに配置することができます
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
    user_id = event.source.user_id 

    if user_message == "おはようございます":
        reply_with_carousel(event)
    else:
        reply_with_text(user_id, user_message)
    

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)