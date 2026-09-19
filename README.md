# JINKAKU

**ローカル推論を中心に、人格・長期記憶・自発会話を組み合わせた Android 向け人格AI。**

現在の通常チャットは **Gemma 4 E2B LiteRT-LM / GPU + MTP** を使用します。会話、Persona、Memory は基本的に端末内で処理・保存し、必要なときだけモデル取得、アプリ更新、任意のWeb検索で外部通信します。

Current release: **v0.1.82 build 352**

AI / coding agents: start with **[AGENTS.md](AGENTS.md)** before analyzing or modifying the repository.

> JINKAKU は「高度な調べ物をするクラウドAI」よりも、端末内で自然に会話を続け、人格と記憶を持たせることを重視した個人向けプロジェクトです。

## 主な機能

### ローカルチャット
- Gemma 4 E2B LiteRT-LM をメインチャットに使用
- LiteRT-LM の **GPU + MTP 固定**ランタイム
- Context は最大 **8K**
- Thinking ON / OFF
- Context量に応じたThinking budget
- Top-K / Top-P / Temperature 調整
- 直前回答との過度な類似を検出して再生成する反復抑制
- 生成停止に対応

### 推論テレメトリ
チャット画面で推論状態を確認できます。

- Context使用量
- PREFILL / THINKING / DECODE
- TTFT
- Prefill tok/s
- Decode tok/s
- 生成token数
- Backend表示

Contextメーターは LiteRT-LM の token count を使って更新します。

### Persona
JINKAKU の性格、口調、ユーザーとの距離感、ルールを自由に設定できます。

さらにローカルのPersonaジェネレーターを搭載しています。

- 完全ランダム生成
- 既存Personaのミューテーション
- テーマ選択
- Chaos 0–100%
- 生成結果は保存ボタンを押すまで現在のPersonaへ反映しない

### 長期Memory
通常チャットとは別に長期記憶をSQLiteへ保存します。

主なMemory種別:

- USER
- SELF
- RELATIONSHIP
- EPISODIC
- PREFERENCE
- PROJECT
- PERSONA

Memoryには「誰についての記憶か」という所有者情報を持たせ、USERの記憶をJINKAKU自身の体験として誤認しにくい構造にしています。

Memory画面から手動追加・確認も可能です。

### 独り言モード
チャット画面を開いたまま一定時間操作がないと、JINKAKUがPersonaや直近の会話を参照して短い独り言を生成します。

モード:

- OFF
- 控えめ
- 普通
- よく喋る

入力、送信、スクロールなどで待機タイマーはリセットされます。独り言は通常のユーザー発言として扱わず、Memory抽出対象にも入れません。

### Web検索
必要な場合だけ **Tavily** を使ってWeb検索できます。

- OFF
- 手動
- 自動
- Basic / Advanced
- API keyは端末内に保存
- 検索失敗時はローカル回答へフォールバック
- Web情報は外部の未信頼コンテキストとしてプロンプトへ挿入

通常のローカル会話だけならTavilyは不要です。

### スーパーメンヘラモード
通常チャットとは完全に分離した会話ゲームです。

- 100チャット以内の安定化を目指す独立モード
- 専用Persona
- セッション専用Memory
- 通常のPersona / Memory / Web / 会話DBへ保存しない
- 終了時にゲーム用状態を破棄
- Thinkingを使用
- 6K–8K Context
- 直近回答の重複を検出し、必要なら1回だけ自動再生成

実験的な会話モードなので、通常チャットのMemoryを汚さず試せます。

### UIカスタマイズ
- Dark / Light
- 2色アクセントを個別設定
- 前景色の自動コントラスト調整
- AI吹き出し横アイコン切替
- 文字サイズ変更
- Liquid Glass系UI
- Adaptive Icon

### アプリ内更新
GitHub Releasesから更新確認、APK取得、インストールまで行えます。

更新APKはアプリ側でダウンロードし、進捗を表示します。通信が途切れた場合の再開にも対応しています。

## モデル

### Main chat / Memory worker

`litert-community/gemma-4-E2B-it-litert-lm`

使用ファイル:

```
gemma-4-E2B-it.litertlm
```

現在の通常チャットは **E2B LiteRT-LM only** です。リポジトリには過去のE4B実装や互換用コードも残っていますが、通常のメインチャット経路ではE2Bを使います。

### Embedding

`EmbeddingGemma 300M GGUF` の読み込みに対応しています。

使用ファイル:

```
embeddinggemma-300M-qat-Q4_0.gguf
```

モデルはAPKに含めません。設定画面からダウンロードするか、端末内ファイルを指定して読み込みます。

## 使い方

1. Settings → **モデル** から E2B LiteRT-LM を導入
2. **Persona** に性格・口調・呼び方・ルールを設定
3. そのままチャット開始
4. 必要なら Memory を手動追加
5. Context / Thinking / Top-K / Top-P / Temperature を好みに合わせて調整
6. 最新情報が必要な場合だけ Tavily Web検索を設定

最初は **モデル → Persona → チャット** だけで十分です。

## 対応環境

- Android 13 / API 33 以上
- arm64-v8a
- targetSdk 36
- compileSdk 36

LiteRT-LMのGPU + MTPを前提にしているため、端末GPUやドライバとの相性によっては初期化できない場合があります。現在のメインチャットはCPUやMTP OFFへの自動フォールバックを行いません。

## データと通信

通常チャット、Persona、Memoryなどの主要データは端末内に保存します。

外部通信が発生する主なケース:

- Hugging Faceからのモデル取得
- GitHub Releasesの更新確認 / APK取得
- Tavily Web検索を有効にした場合

Tavily検索では検索クエリを外部へ送信します。Web検索をOFFにすれば、通常会話のためにTavilyへ通信することはありません。

## バックアップとログ

- SQLite WAL checkpoint付きバックアップ
- ログエクスポート
- 0 byteログを避けるためのflush / sync
- Android Auto Backup / device transferからアプリデータを除外

## ビルド

必要環境:

- JDK 17
- Gradle 8.13
- Android SDK 36
- NDK 29.0.13113456
- CMake 3.31.6

```bash
gradle :app:assembleRelease
```

ただし、JINKAKUは保存されているKotlinソースへ複数のPythonパッチを順番に適用して最終ソースを生成する構成です。

そのため、素の `assembleRelease` だけではGitHub Releasesと同じAPKにならない場合があります。現在の正しいパッチ順は次を参照してください。

- `.github/workflows/android.yml`
- `docs/CHAT_HANDOFF.md`

開発をChat / Codexへ引き継ぐ場合も `docs/CHAT_HANDOFF.md` を先に確認してください。

## GitHub Actions

`main` へのpushでAndroid Release workflowが動きます。

通常のリリースpushでは:

1. legacy source patchesを順番に適用
2. E2B-only変換と現行パッチを適用
3. release APKをビルド
4. `version.json` を生成
5. GitHub ReleaseへAPKをアップロード

ドキュメントだけを更新する場合は、不要なAPKビルドを避けるためコミットメッセージに `[skip ci]` を付ける運用を推奨します。

## 署名

個人利用とアプリ内上書き更新を優先し、v0.xではリポジトリ内の固定keystoreでrelease APKを署名しています。

**公開リポジトリ内に鍵があるため、公開配布向けの強い署名セキュリティはありません。**

第三者向けに正式配布する場合は、秘密鍵をリポジトリ外で管理する方式へ移行してください。

## 開発メモ

JINKAKUは現在も高速に仕様変更しているため、古いソースコメントやlegacy E4Bコードが残っている場合があります。

実際の現行挙動を確認するときは、次の順で見るのが確実です。

1. `.github/workflows/android.yml`
2. workflowで最後に適用されるpatch
3. `app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt`
4. 最新GitHub Release

人類はコードよりREADMEを先に老化させがちなので、このREADMEでは「現在のReleaseで実際に使う経路」を優先して記載しています。
