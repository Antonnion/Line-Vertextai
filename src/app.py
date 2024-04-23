import os
import config
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
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
    columns = [
        CarouselColumn(
            thumbnail_image_url="https://example.com/bot/images/item1.jpg",
            title="アルバイト＆パート",
            text="下記の中から選択してください。",
            actions=[
                PostbackAction(label="シフト入力", data="action=shift_input"),
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

def generate_next_month_schedule():
    # 現在の日付を取得
    now = datetime.now()
    # 現在の月の最後の日を取得
    _, last_day_of_current_month = calendar.monthrange(now.year, now.month)
    # 次の月の第一日を計算
    first_day_of_next_month = datetime(now.year, now.month, last_day_of_current_month) + timedelta(days=1)

    # 次の月の日程を生成
    dates = []
    for i in range(calendar.monthrange(first_day_of_next_month.year, first_day_of_next_month.month)[1]):
        day = first_day_of_next_month + timedelta(days=i)
        formatted_date = day.strftime(f"{day.month}月{day.day}日 (%a) 00:00 ~ 00:00")
        dates.append(formatted_date.replace(day.strftime('%a'), ['月', '火', '水', '木', '金', '土', '日'][day.weekday()]))

    return "\n".join(dates)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "action=shift_check":
        # シフト情報を取得する関数を呼び出し
        shift_info = generate_next_month_schedule()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"シフト情報: {shift_info}")
        )
    elif data == "action=some_other_action":
        # 別のアクションに対する応答
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="何らかの他の情報をここに返す")
        )

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