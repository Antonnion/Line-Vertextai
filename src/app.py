import os
import config
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine
from linebot.models import (
    DatetimePickerAction, MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URIAction, PostbackAction, MessageAction, PostbackEvent
)
from google.cloud import bigquery
from google.cloud import aiplatform as vertexai
from vertexai.language_models import CodeGenerationModel
from vertexai.language_models import TextGenerationModel


from datetime import datetime, timedelta
import calendar

app = Flask(__name__)

# LINE Bot APIとWebhook Handlerの初期化
line_bot_api = LineBotApi(config.token)
handler = WebhookHandler(config.secret)

# Google CloudのプロジェクトID、ロケーション、データストアIDの設定
PROJECT_ID = config.project_id
LOCATION = config.location
DATA_STORE_ID = config.datastore
now = datetime.now()
# Google Discovery Engineのクライアントを取得する関数
def get_client():
    client_options = (
        ClientOptions(api_endpoint=f"{LOCATION}-discoveryengine.googleapis.com")
        if LOCATION != "global"
        else None
    )
    return discoveryengine.SearchServiceClient(client_options=client_options)

# 検索要約を取得する関数
def search_summaries(client, search_query: str) -> str:
    serving_config = client.serving_config_path(
        project=PROJECT_ID,
        location=LOCATION,
        data_store=DATA_STORE_ID,
        serving_config="default_config",
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=search_query,
        page_size=3,
        content_search_spec={
            "summary_spec": {
                "summary_result_count": 3,
                "ignore_non_summary_seeking_query": True,
                "ignore_adversarial_query": True
            },
            "extractive_content_spec": {
                "max_extractive_answer_count": 1
            }
        }
    )
    response = client.search(request)
    app.logger.info(f"Full Vertex AI response: {response}")
    return response.summary.summary_text if response.summary else "該当する結果は見つかりませんでした。"


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    date_time = event.postback.params['datetime']  # ユーザーが選択した日時

    # ポストバックデータと日時を使って何か処理を行う
    # 例えばユーザーに選択された日時を確認のメッセージとして送り返す
    response = reply_with_text(user_id, date_time)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

    
def reply_with_text(user_id, date_time: str) -> str:
    vertexai.init(project="ca-sre-bpstudy1-kishimoto-dev", location="asia-northeast1")
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 1024,
        "temperature": 0.9
    }
    model = CodeGenerationModel.from_pretrained("code-bison-32k@002")
    response = model.predict(
        prefix=f"You are an experienced data analyst. Write a BigQuery SQL to answer the user's prompt based on the following context:\n"
               "Create and execute the following SQL query based on the information provided by the user.\n"
               "The data to be inserted is based on the information provided by the user. \n"
               "For example, if the user provided shift information for April 12, 2022 from 10:00 am to 5:00 pm with an user ID of 4, use the following query\n"
               "INSERT INTO `ca-sre-bpstudy1-kishimoto-dev.employee_data.kk`\n"
               "(user_id, shiftdate, start_time, end_time)\n"
               "VALUES\n"
               "(4, '2022-04-12', '10:00:00', '17:00:00');\n"
               "---- Context ----\n"
               "Format: Plain SQL only, no Markdown\n"
               "Table: ca-sre-bpstudy1-kishimoto-dev.employee_data.kk\n"
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
               f"User's prompt: {user_id}, {date_time}",
        **parameters
    )
    # Ensure the response is a string, modify based on your response structure
    return response.text if hasattr(response, 'text') else str(response)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

def reply_with_text(event):
    client = get_client()
    bot_response = search_summaries(client, event.message.text)
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=bot_response))
    except Exception as e:
        app.logger.error(f"Error in reply_message: {e}")

def reply_with_carousel(event):
    initial_date = now.strftime('%Y-%m-%dT%H:%M')
    min_date = (now - timedelta(days=365)).strftime('%Y-%m-%dT00:00')  # 1年前
    max_date = (now + timedelta(days=365)).strftime('%Y-%m-%dT23:59')  # 1年後
    columns = [
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="アルバイト＆パート",
            text="下記の中から選択してください。",
            actions=[
                DatetimePickerAction(
                    label="シフト入力",
                    data="action=shift_input&item_id=123",
                    mode="datetime",
                    initial=initial_date,
                    min=min_date,
                    max=max_date
                ),
                MessageAction(label="アンケート開始", text="アンケートを開始します"),
                URIAction(label="View detail", uri="https://my-service-d6nkubzq2q-uc.a.run.app")
            ]
        ),
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item2.jpg",
            title="正社員",
            text="下記の中から選択してください。",
            actions=[
                PostbackAction(label="シフト入力", data="action=shift_input&item_id=123"),
                PostbackAction(
                    label="Buy",
                    data="action=shift_input&item_id=123",
                    displayText="Buy",
                    inputOption="openKeyboard",
                    fillInText="---\nName: \nPhone: \nBirthday: \n---"
                ),
                URIAction(label="View detail", uri="https://my-service-d6nkubzq2q-uc.a.run.app")
            ]
        ),
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="管理者用",
            text="下記の中から選択してください。",
            actions=[
                MessageAction(label="シフト確認", text="シフトを表示してください"),
                MessageAction(label="アンケート開始", text="アンケートを開始します"),
                URIAction(label="View detail", uri="https://my-service-d6nkubzq2q-uc.a.run.app")
            ]
        ),
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

    if user_message == "おはようございます":
        reply_with_carousel(event)
    else:
        reply_with_text(event)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)