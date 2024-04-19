FROM python:3.8-slim

# 作業ディレクトリの設定
WORKDIR /src

# 依存関係のコピーとインストール
COPY /src/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY /src .

# ポートの公開
EXPOSE 8080

# コンテナ起動時に実行されるコマンド
CMD ["python", "app.py"]