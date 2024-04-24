import os
import config
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from vertexai.language_models import TextGenerationModel
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine, bigquery, aiplatform as vertexai
from linebot.models import (
    DatetimePickerAction, MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URIAction, PostbackAction, MessageAction, PostbackEvent
)


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
@handler.add(PostbackEvent)
def handle_postback(event):
    date_time = event.postback.params['datetime']  # ユーザーが選択した日時

    # ポストバックデータと日時を使って何か処理を行う
    # 例えばユーザーに選択された日時を確認のメッセージとして送り返す
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f" {date_time} を送信。")
    )
    #reply_with_text(event)

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
                PostbackAction(label="シフト入力", data="action=shift_input"),
                MessageAction(label="アンケート開始", text="アンケートを開始します"),
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

def reply_with_text(event):
    user_message = event.message.text
    user_id = event.source.user_id
    model = TextGenerationModel.from_pretrained("text-bison@002")
    vertexai.init(project="ca-sre-bpstudy1-kishimoto-dev.employee_data.kk", location="asia-northeast1")
    final_response = "Sorry, an error occurred."
    prompt = (f"You are an experienced data analyst. Write a BigQuery SQL to answer the user's prompt based on the following context:\n"
               "Create and execute the following SQL query based on the information provided by the user.\n"
               "The data to be inserted is based on the information provided by the user. \n"
               "For example, if the user provided shift information for April 12, 2022 from 10:00 am to 5:00 pm with an employee ID of 4, use the following query\n"
               "INSERT INTO `ca-sre-bpstudy1-kishimoto-dev.employee_data.kk`\n"
               "(employee_id, shiftdate, start_time, end_time)\n"
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
               f"User's prompt: {user_id}, {user_message}")
    response = model.predict(prompt, candidate_count=1, max_output_tokens=1024, temperature=0.9)

    # 応答からSQLクエリを取得
    sql_query = response.text.strip() if hasattr(response, 'text') else str(response)
    if sql_query:
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    # BigQueryクライアントの初期化
    client = bigquery.Client()

    try:
        # SQLクエリを実行
        query_job = client.query(sql_query)
        query_job.result()  # 実行結果を待つ
        return "Insertion to BigQuery was successful."
    except Exception as e:
        return f"Failed to execute query: {e}"
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)