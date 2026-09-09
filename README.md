# Jinkaku

完全ローカルを基本としたAndroid人格AIです。メイン会話は **HauhauCS Gemma 4 E4B Uncensored GGUF**、長期記憶の抽出・整理は **Gemma 4 E2B LiteRT-LM** が担当します。

Chat / Codexで変更を引き継ぐ場合は、[変更・ワードマーク差し替え手順](docs/CHAT_HANDOFF.md) を参照してください。
ビルド時のPythonパッチ、編集対象、画像変換、GitHubへの反映、検証・更新配布の手順をまとめています。

## v0.1.0 MVP

- E4B Q4_K_M GGUFをアプリからダウンロードしてローカル推論
- Thinking/CoTは内部で使用し、通常UIや会話DBには保存・表示しない
- E2B LiteRT-LMを会話中は常駐させず、アイドル時にMemory候補を抽出
- User / Self / Relationship / Episodic / Preference / Project Memory用SQLite DB
- 256次元Hashing Embedding + keyword/entity hybrid retrieval
- Context 4K / 8K / 16K / 32K切替（初期8K）
- GitHub Releasesからアプリ内更新
- 常時追記・flush/sync付きログエクスポート。0 byteログを禁止
- SQLite WAL checkpoint付きバックアップ
- Android Auto Backup / device transferからアプリデータを除外

## モデル

Main: `HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive` の `Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf`

Memory worker: `litert-community/gemma-4-E2B-it-litert-lm` の `gemma-4-E2B-it.litertlm`

モデルはAPKに含めません。設定画面から取得します。

## Embeddingについて

EmbeddingGemma 300MはHugging Face側でライセンス同意が必要なため、匿名ダウンロード前提の初期版には直接組み込んでいません。MVPでは`HashingEmbeddingEngine`を代替として使用し、固有名詞検索も併用します。後からEmbeddingGemma実装へ置き換えられる構造です。

## ビルド

JDK 17 + Gradle 8.13 + Android SDK 36。NDK・CMakeの指定は `.github/workflows/android.yml` を参照してください。

**ビルド前に、最新ワークフローの `Apply CPU runtime patches` ステップ全体を適用してください。**
保存されているベースソースへ複数のPythonパッチを順番に適用してから、APKを作る構成です。
ローカルでの再現方法は [引き継ぎ手順](docs/CHAT_HANDOFF.md#5-パッチ適用ビルドの確認方法) を参照してください。

```bash
gradle :app:assembleRelease
```

`main`へのpushでGitHub Actionsがrelease APKを作成し、同一バージョンのGitHub Releaseへアップロードします。

## 署名

個人利用とアプリ内上書き更新を優先し、v0.xではリポジトリ内の固定keystoreでrelease APKを署名します。**公開リポジトリに鍵があるため、強いセキュリティはありません。** 公開配布する場合は秘密鍵管理へ移行してください。

## データ

通常チャットとMemoryは端末内SQLiteに保存します。外部通信はモデル取得・GitHub Release更新確認/取得に限定しています。
