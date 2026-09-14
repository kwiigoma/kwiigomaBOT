# kwiigonaBOT v8

Discord bot combining:
- 🎁 GomaLog
- 🎥 くぃチューバー
- 🏢 会社・株式市場
- ⚔️ Battle（対人アキネーター風推理ゲーム）

## Battle
- Botが秘密のお題を自動選択
- YES / NO / わからないで質問に回答
- `/battle質問` → `/battle回答` → `/battle推理`
- 勝利でBattle PointとBattleアイテムを獲得
- Rating / ランク / 勝率 / 連勝を記録
- `/battleランダム` は全サーバー共通の待機列
- `/battleランクマッチ` はRating差±250以内を優先
- BattleデータはDiscordサーバーIDではなくユーザーID中心で保存するため、サーバーをまたいで利用可能
- すべてのスラッシュコマンドのBot返信はエフェメラル
- Battleの対戦通知は必要な相手にDMで送信

## Battleアイテム
- 攻撃：追加質問カード / ヒントカード / 回答強制カード
- 防御：ガードカード / 質問変更カード / 情報隠蔽カード

## 環境変数
`DISCORD_TOKEN` にDiscord Bot Tokenを設定してください。

## 起動
```bash
pip install -r requirements.txt
python main.py
```
