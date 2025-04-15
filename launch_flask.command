#!/bin/bash
cd "$(dirname "$0")"

# 🚫 セキュリティの隔離フラグがあれば自分自身から削除
xattr -d com.apple.quarantine "$0" &>/dev/null

# ✅ Python3 チェック
if ! command -v python3 &>/dev/null; then
  osascript -e 'display alert "Python3が見つかりません" message "このアプリを使うにはPython3が必要です。"'
  exit 1
fi

# ✅ モジュール確認・自動インストール
osascript -e 'display dialog "必要なパッケージを確認・インストール中です。\n1回目だけ少し時間がかかります。" buttons {"OK"}'
python3 -m pip install --user flask PyPDF2 Pillow &>/dev/null

# ✅ インストール完了メッセージ
osascript -e 'display notification "必要な準備が完了しました！" with title "PDFツール 起動準備OK"'

# ✅ Flask アプリ起動
python3 app.py
