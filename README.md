# 生理予測アプリケーション

## 概要
個人の記録（体調、トイレ、服薬など）を集約し、周期予測・変化点検出・簡易機械学習モデルで日次の「高確率日」を推定するローカル/コンテナ実行向けアプリケーション。

## 主要機能
- 日次エントリの集約と要約
- 変化点検出（ruptures）と HMM による候補抽出
- 疑似ラベル生成と自己学習型分類器（LightGBM / RandomForest）
- 個別モデルの保存と予測分布の融合
- 服薬候補のカテゴリ正規化と検索スコアリング
- プロビジョナル期間の作成・評価・確定による周期更新

## 開発環境（推奨）
- Docker / docker-compose を利用したコンテナ実行
- Python 3.11+

## クイックスタート（Docker）
1. リポジトリをクローンする  
2. `.env.example` をコピーして `.env` を作成し、必要な値を設定する  
3. `docker-compose up --build` を実行する  
4. Web サービスは `http://localhost:8000` で待ち受ける

## ローカル実行（仮想環境）
1. 仮想環境を作成して有効化する  
2. `pip install -r requirements.txt`  
3. 環境変数を設定（`.env` を読み込むかエクスポート）  
4. DB と Redis を用意する（docker-compose を推奨）  
5. マイグレーションを実行して DB を初期化する（Alembic）  
6. `gunicorn -b 0.0.0.0:8000 app:create_app()` で起動

## スクリプト
- `scripts/seed_meds_list.py` — meds_list のシード/マージ
- `scripts/migrate_json_to_db.py` — `individual_data/*.json` を DB に移行するユーティリティ（dry-run 推奨）

## 運用上の注意
- `meds_list.json` はカテゴリ形式またはフラット配列の両方を読み取れるが、内部では**フラット配列に正規化**して扱う。上書き前に必ずバックアップを取ること。  
- 機械学習関連はローカルの履歴データに依存するため、学習前に履歴が十分に蓄積されているか確認すること。  
- 個人データを扱うため、保存先のアクセス制御と TLS を必ず確保すること。

## テストと検証
- 小規模なダミーデータで `features.extract_features_from_history`、`ml.train_self_training_classifier_for_uid`、`provisional.finalize_provisionals` を順に実行して統合動作を確認する。  
- `meds` 機能は `scripts/seed_meds_list.py` でカテゴリ JSON を正規化してから `services.meds.suggest_meds` を呼び出して候補の順位を検証する。

## トラブルシューティング
- 依存ライブラリのビルドに失敗する場合は OS パッケージ（`build-essential`, `libpq-dev` 等）を確認する。  
- Celery がジョブを拾わない場合は `CELERY_BROKER_URL` と `CELERY_RESULT_BACKEND` の設定を確認する。  
- モデル保存に失敗する場合は `models/` ディレクトリの書き込み権限を確認する。

## 連絡
実行中にエラーが出たら、エラーログ（web / worker / redis / db）を用意して報告してください。どの機能を先に動かして検証したいですか？