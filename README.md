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
- `archive/YYYYMMDD/post_*.png`
- `archive/YYYYMMDD/caption_*.txt`
- `archive/YYYYMMDD/result_*.json`
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
   - `output/latest.png` は常に最新固定名として更新
   - 履歴画像は `archive/YYYYMMDD/post_*.png` に保存
   - 人物ありは左配置 + BTC 右配置
   - 人物画像が取れない前提でも代替ポートレートで完走
5. `scoring.py`
   - 変動率、話題性、人物有無でスコアリング
6. `improver.py`
   - `best_result.json` を参照して改善案を追加
   - 低スコア時は訴求や人物補完を強化

## GitHub Actions / PR運用

### Workflow 名
- `PR Validation`

### 必須チェック名
- `pipeline-smoke (ubuntu-latest)`
- `pipeline-smoke (windows-latest)`
- `regression-guards`

### PR作成時に自動実行される内容
- Python セットアップ
- 依存関係インストール（`requirements.txt` / `requirements-dev.txt` がある場合のみ）
- `python main.py --output-dir ci_output`
- 生成物確認
  - `ci_output/latest.png`
  - `ci_output/latest.txt`
  - `ci_output/best_result.json`
- 回帰ガード
  - long URL を含む caption 生成がハングしないこと
  - `latest.png` / `latest.txt` / `best_result.json` の整合性確認

### Codex review 前提の運用
- PR テンプレートに従って Codex review を依頼します。
- Actions の必須チェックがすべて green になってから GitHub auto-merge を有効化します。

### コードで追加した範囲
- `.github/workflows/pr-validation.yml`
- `.github/pull_request_template.md`
- `tests/test_ci_guards.py`
- `tests/verify_artifacts.py`
- `tests/optional_pip_install.py`

### GitHub 側で手動設定が必要な項目
以下はリポジトリ設定で人手対応が必要です。

1. **Branch protection rule** を対象ブランチに設定
2. **Require a pull request before merging** を有効化
3. **Require status checks to pass before merging** を有効化
4. Required status checks に以下を登録
   - `pipeline-smoke (ubuntu-latest)`
   - `pipeline-smoke (windows-latest)`
   - `regression-guards`
5. 必要なら **Require approvals** を有効化し、Codex review または人間レビューを運用ルール化
6. **Allow auto-merge** を有効化
7. Merge strategy は **Squash merge 推奨**、履歴重視なら **Rebase merge** を許可、通常の merge commit は極力使わない

### auto-merge まで有効化する具体手順
1. GitHub で `Settings` → `General` → `Pull Requests` を開く
2. `Allow auto-merge` を ON にする
3. `Settings` → `Branches` → 対象ブランチの protection rule を作成/更新
4. `Require status checks to pass before merging` を ON
5. 上記3つのチェック名を required checks に追加
6. 必要なら review approval 条件も設定
7. 推奨 merge strategy を設定（`Squash merge` 推奨、必要なら `Rebase merge`）
8. PR を作成し、Codex review を実施
9. `PR Validation` が全 green になったら PR 画面で `Enable auto-merge` を押す

## 注意

- 外部通信が失敗した場合でもサンプルにフォールバックします。
- エラー時もログを残し、停止しにくい構成にしています。
- 画像生成は追加依存なしで動くよう、標準ライブラリのみで PNG を書き出します。

## 出力保存の考え方

- `output/latest.png` / `output/latest.txt` / `output/best_result.json` は、外部連携や目視確認向けの **最新固定名** です。
- `archive/YYYYMMDD/post_*.png` は、各実行の画像履歴を残すための **履歴保存用** です。
- 同じ日付フォルダには `caption_*.txt` と `result_*.json` も保存されるため、画像だけでなく投稿文と結果JSONも追跡できます。
- そのため「2枚出力される」ように見える場合でも、役割は **latest=現在参照用 / post_*=履歴保存用** に分かれています。

## 日替わり化した要素

- `news_fetcher.py` はその日のニュース記事に加えて BTC 価格/24時間変化率も取得し、失敗時はサンプルへフォールバックします。
- `ai_extract.py` は `person.name`, `person.role`, `person.summary` を含む人物プロフィールを生成します。
- `main.py` の最終JSONには `person`, `article`, `market` の要約フィールドが追加されます。
- `generate_image.py` は日ごとの記事内容に応じて、ヘッドライン、人物名、人物説明、BTC価格、BTC変化率、市場ムード配色を更新します。
