import os
import config
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage,
    CarouselTemplate, CarouselColumn, URIAction, PostbackAction
)

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

# Line request -> Vertex AI -> Line responce
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text

    # 商品を見るというリクエストに対するカルーセル応答
    if user_message == "商品を見る":
        columns = [
            CarouselColumn(
                thumbnail_image_url="https://example.com/bot/images/item1.jpg",
                title="this is menu",
                text="description",
                actions=[
                    PostbackAction(label="Buy", data="action=buy&itemid=111"),
                    PostbackAction(label="Add to cart", data="action=add&itemid=111"),
                    URIAction(label="View detail", uri="http://example.com/page/111")
                ]
            ),
            CarouselColumn(
                thumbnail_image_url="https://example.com/bot/images/item2.jpg",
                title="this is menu",
                text="description",
                actions=[
                    PostbackAction(label="Buy", data="action=buy&itemid=222"),
                    PostbackAction(label="Add to cart", data="action=add&itemid=222"),
                    URIAction(label="View detail", uri="http://example.com/page/222")
                ]
            ),
            # 追加のカラムなどをここに配置
        ]
        carousel_template = CarouselTemplate(columns=columns)
        template_message = TemplateSendMessage(
            alt_text='Carousel template',
            template=carousel_template
        )
        line_bot_api.reply_message(event.reply_token, template_message)

    # 他のメッセージに対する標準応答
    else:
        client = get_client()
        bot_response = search_summaries(client, user_message)
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=bot_response))
        except Exception as e:
            app.logger.error(f"Error in reply_message: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)