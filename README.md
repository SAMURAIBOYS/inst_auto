# insta_auto

仮想通貨ニュースを元に、毎回更新される **投稿文 + 画像** を自動生成するスクリプトです。

## 実行

```bash
python main.py
```

実行すると次を更新します。

- `output/latest.png`
- `output/latest.txt`
- `output/best_result.json`
- `output/logs/attempt_01.json`
- `output/logs/attempt_02.json`（必要時）

## 主要機能

1. `news_fetcher.py`
   - API → RSS → ローカルサンプルの順でニュース取得
   - API キー未設定でも完走
2. `ai_extract.py`
   - 固定 JSON を返却
   - `Bitcoin` があれば `Satoshi Nakamoto` を補完
   - `BlackRock` などの組織名から代表人物を補完
3. `generate_caption.py`
   - `claim_summary` ベース
   - フック、短文、改行、感情ワードを追加
   - X 向け 100〜180 文字を目安に調整
4. `generate_image.py`
   - 毎回新しい PNG を保存し `latest.png` を更新
   - 人物ありは左配置 + BTC 右配置
   - 人物画像が取れない前提でも代替ポートレートで完走
5. `scoring.py`
   - 変動率、話題性、人物有無でスコアリング
6. `improver.py`
   - `best_result.json` を参照して改善案を追加
   - 低スコア時は訴求や人物補完を強化

## 注意

- 外部通信が失敗した場合でもサンプルにフォールバックします。
- エラー時もログを残し、停止しにくい構成にしています。
- 画像生成は追加依存なしで動くよう、標準ライブラリのみで PNG を書き出します。
