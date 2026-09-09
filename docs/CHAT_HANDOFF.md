# Chat / Codex向け：Jinkakuの変更・ワードマーク差し替え手順

この文書は **v0.1.53 / versionCode 54** の実装を基準にした引き継ぎ資料です。
以後の作業では、最初に最新の `main` と `.github/workflows/android.yml` を確認してください。

リポジトリ：<https://github.com/IKEGAMI-99/jinkaku>

新しいChatへ引き継ぐときは、この文書のURLと変更内容・添付画像を渡せます。
実際にGitHubへ反映するには、そのChatで対象リポジトリへの読み書きができる接続・ツールが必要です。
文書を読めることとGitHubを書き換えられることは別なので、反映できていない変更を「反映済み」と報告しないでください。

## 1. 最初に知っておく構成

**リポジトリ内のKotlinはベースソースです。リリースAPKは、そこへ複数のPythonパッチを適用して作られます。**

`MainActivity.kt` は `ModernJinkakuApp(vm)` を起動します。
保存されている `ModernJinkakuApp.kt` だけでは、現在のヘッダーや色・ボタンなどの完成形を確認できません。
`BrandedJinkakuApp.kt` など別のUIも存在するため、名前の印象で編集先を選ばず、起動経路を確認します。

現行のGitHub Actionsは次の順序で動きます。

1. リポジトリをcheckoutし、Java・Android SDK・NDK・CMakeを準備。
2. `Apply CPU runtime patches` ステップでPythonパッチを順番に実行。
3. パッチ適用後のソースを `gradle --no-daemon :app:assembleRelease` でビルド。
4. `gradle.properties` からバージョンを読み、APKと `version.json` を作成。
5. PRでは検証用artifactを保存。`main`へのpushまたは手動実行ではGitHub Releaseにも公開。

パッチの一部は既存コードの文字列を完全一致で置換します。先に古いソースやパッチの置換元を変えると、
後続パッチが `anchor not found` などで止まることがあります。
**既存のパッチを順番ごと取り除いたり、適用後の全ソースをそのままベースへ上書きしたりしないでください。**

## 2. ワードマークに関係するファイル

| ファイル | 役割・編集判断 |
| --- | --- |
| `app/src/main/res/drawable-nodpi/jinkaku_header_wordmark.png` | 現在のヘッダー専用画像。絵柄だけの差し替えはここを置換する。 |
| `scripts/patch_v053_wordmark.py` | ヘッダーの参照先と表示枠を変更する最終パッチ。v052の後に実行される。 |
| `scripts/patch_v041_wordmark_png.py` | PNG読み込みと失敗時の文字表示をベースソースへ追加する。後続パッチがこの出力に依存する。 |
| `app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt` | パッチ適用先のUIベースソース。完成形は適用後の内容で確認する。 |
| `.github/workflows/android.yml` | 実際のパッチ順・ビルド・配布処理の正本。 |
| `gradle.properties` | `JINKAKU_VERSION_NAME` と `JINKAKU_VERSION_CODE`。更新配布時に変更する。 |
| `app/src/main/res/drawable-nodpi/jinkaku_wordmark_png.png` | 旧画像。アプリアイコンにも参照されるので、ヘッダーだけの差し替えでは触らない。 |

アプリアイコンは `AndroidManifest.xml` の `@mipmap/jinkaku_app_icon` から、
adaptive icon → `drawable/jinkaku_icon_foreground.xml` → 旧 `jinkaku_wordmark_png.png` と参照されます。
旧画像には `jinkaku_launcher_icon.xml` からの参照もあります。
この共有を避けるため、v0.1.53でヘッダー専用画像を別名で追加しました。

## 3. v0.1.53で何をしたか

元の添付ファイルは、名前が `.png` でも実体は **JPEG / RGB / 1536×512** でした。
そのままPNGリソースとして配置せず、PNGへ実際に再エンコードしています。
添付の絵柄を使用し、画像生成は行っていません。

- 画像サイズは1536×512を維持し、減色しないRGBA PNGに変換。
- 黒背景を透過化。元のRGB値は保持し、透明度だけを変更。
- ヘッダー専用の `jinkaku_header_wordmark.png` として追加。
- `patch_v053_wordmark.py` がヘッダーの読み込み先を `R.drawable.jinkaku_header_wordmark` に変更。
- 表示枠を `144.dp × 48.dp`、表示方法を `ContentScale.Fit` にして3:1の縦横比を維持。
- 既存の `BitmapFactory.decodeResource` → `asImageBitmap()` と `runCatching` による読み込みを維持。
  読み込めなかった場合は既存の `Text("JINKAKU", ...)` が表示される。
- バージョンを `0.1.53` / `54` に更新。

現在の画像は約699KBです。以前の160×53・16色の画像を拡大したものではありません。

### 今回の画像変換を再現する場合

以下は**今回の、黒背景のRGB画像に使った変換**です。PillowとNumPyがあるローカル環境で実行します。
実行時の `source` を、実在する添付ファイルのパスに置き換えてください。

```python
from pathlib import Path
from PIL import Image
import numpy as np

source = Path("/path/to/attached-image.png")
destination = Path("app/src/main/res/drawable-nodpi/jinkaku_header_wordmark.png")

with Image.open(source) as image:
    print("Actual format:", image.format, "Mode:", image.mode, "Size:", image.size)
    rgb = np.asarray(image.convert("RGB"))

brightness = rgb.max(axis=2).astype(np.float32)
alpha = np.clip((brightness - 20) * 255 / 25, 0, 255).astype(np.uint8)
rgba = np.dstack((rgb, alpha))
Image.fromarray(rgba).save(destination, format="PNG", optimize=True)

with Image.open(destination) as image:
    image.verify()
```

最大RGB値20以下を透明、45以上を不透明とし、その間を滑らかにつないでいます。
**これは汎用の背景除去ではありません。** 黒い文字・影・暗い絵柄のある別画像にそのまま使うと、それらも消えます。
すでに正しい透過PNGなら、既存のアルファを保ってそのまま利用するか、RGBA PNGとして保存します。
白背景など別条件の画像にこのしきい値を流用しないでください。

## 4. 次にワードマークを差し替える手順

1. 最新の `main`、現在のバージョン、作業中のPRを確認する。既存のユーザー変更がある場合は別ブランチ・作業コピーで作業する。
2. 添付ファイルが実際に存在することを確認し、画像を開いて実形式・解像度・透過を調べる。
3. 新しい絵柄を `jinkaku_header_wordmark.png` へ保存する。PNGはバイナリとして扱い、元画像の画質を保つ。
4. 同じ3:1の絵柄で現在の大きさが適切なら、表示用パッチは変更しなくてよい。
5. 縦横比・表示サイズも変える場合は、現在の後続パッチへの影響を検索してから表示枠を調整する。
   v053を編集するなら `new` 側の出力を調整し、`old` 側の置換元と前段パッチの出力を一致させたままにする。
   適用済み判定の `marker` と出力内コメントも一致させる。画像は `ContentScale.Fit` で収め、上部バーや隣のボタンとの収まりを確認する。
6. APKを配布する場合は、最新値を基準にバージョン名とコードを進める。`0.1.53 / 54` の次なら例として `0.1.54 / 55`。
   すでにそれより新しい版がある場合は、この例の値を使わない。
7. 次節の手順でパッチ適用とビルドを確認してから、依頼された反映・配布まで進める。

調査に使う検索例：

```bash
rg -n 'jinkaku_header_wordmark|jinkaku_wordmark_png|wordmarkBitmap|WORDMARK_V053' app scripts
rg -n 'JINKAKU_VERSION|Apply CPU runtime patches|patch_v053' gradle.properties .github/workflows/android.yml
```

## 5. パッチ適用・ビルドの確認方法

使い捨ての作業コピーで、**最新ワークフローの `Apply CPU runtime patches` の `run` 全体**を実行します。
v047の直前には、ワークフロー内のPython処理もあります。スクリプト名だけを拾った手順では再現できません。
パッチ適用はKotlin・C++・一部のパッチファイルを書き換えるため、編集内容と検証用の生成差分を混同しないでください。

PyYAMLがある環境なら、リポジトリのルートで次のように、その時点のワークフローから処理を取得できます。

```python
from pathlib import Path
import subprocess
import yaml

workflow = yaml.safe_load(Path(".github/workflows/android.yml").read_text())
step = next(
    step for step in workflow["jobs"]["build"]["steps"]
    if step.get("name") == "Apply CPU runtime patches"
)
subprocess.run(["bash", "-e", "-c", step["run"]], check=True)
```

これはパッチ適用の確認です。APKのビルドには、さらにワークフローに指定されたJava・Gradle・Android SDK・NDK・CMakeが必要です。
適用後、`gradle --no-daemon :app:assembleRelease` を実行します。GitHub Actionsではこれらの環境準備も行われます。

確認する内容：

- パッチがすべて成功し、意図した箇所だけが追加変更される。
- v053のような適用済み判定を持つ新規パッチは、再実行で変更が増えない。
- ヘッダーの参照先とPNGが対応し、同じリソース名を同じ構成のフォルダ内で重複させていない。
- ライト・ダーク両方の背景で、透過・縦横比・切れ・文字の大きさが適切。
- 最新の対象コミットに対するCIが成功する。古いコミットの成功を根拠にしない。
- 必要に応じて完成APKをZIPとして開き、組み込まれた画像が正常にデコードできることを確認する。
  APK内のリソース名は短縮される場合があるため、元のファイル名だけで探さない。
- 実機を使える場合は、既存版への上書き更新、起動、ヘッダー表示、既存データの参照を確認する。
  実機を使えない場合は、未確認であることを報告する。

## 6. GitHub接続から反映する場合

ローカルでgitを使える場合は、通常のブランチ・commit・push・PRで作業できます。
gitへの書き込み接続が使えず、ChatにGitHubの編集ツールがある場合は、次のGit Data API系の処理でも反映できます。
ツールの名前や利用可否は、そのChatで実際に提供されているものを確認します。

1. 対象ブランチの最新コミットSHAとツリーSHAを取得する。
2. PNGの実バイト列をBase64で `create_blob` に渡す。テキスト専用のファイル更新APIにPNGを渡さない。
3. 戻ったblob SHAをローカルの `git hash-object <PNGのパス>` と比較して、転送の一致を確認する。
4. 最新ツリーを `base_tree` にした `create_tree` で、必要なファイルだけを変更する。
5. 最新コミットを親に `create_commit` し、作業ブランチを作成・更新する。force pushを使わず、途中で他の変更が入っていないか再確認する。
6. PRで最新コミットのビルドを確認する。反映が依頼されている場合は、確認したhead SHAを指定してマージする。
7. 配布が必要なら、`main`のビルドとReleaseのAPK・`version.json` まで確認する。

画像データを複数に分けて受け渡すときは、各Base64断片の末尾パディングを含めて文字列連結しないでください。
断片をバイト列へ戻してから全体を再エンコードするか、3の倍数バイトで区切り、最終的なblob SHAで一致を確認します。
これは転送方法の都合で画像を極端に小さくする代わりに用いた方法です。

## 7. 更新配布の扱い

`AppUpdater.kt` はGitHubの最新ReleaseからAPKと `version.json` を取得し、
`version.json` の `versionCode` がインストール済みアプリより大きい場合に更新を案内します。
名前だけを変更してコードを据え置くと、アプリ内更新では新しい版として検出されません。

```json
{"versionName":"0.1.53","versionCode":54,"apk":"jinkaku-v0.1.53.apk"}
```

現行ワークフローは同じタグのassetを `--clobber` で上書きします。
別の変更を同じバージョンのまま公開せず、APKを更新するときはバージョンを進めてください。
既存インストールとの互換性を保つため、ワードマーク変更にアプリID・署名・DB初期化の変更を混ぜません。

文書だけの変更ではAPKのバージョンを進める必要はありません。
現行ワークフローは文書だけのpushでもリリース処理を起動するため、今回の引き継ぎ資料は
文書だけのコミットに `[skip ci]` を付け、APKを再公開しない形で保存しています。
コードや画像変更の検証を省略する用途には使わず、ブランチ保護や必須チェックがある場合はそのルールに従ってください。

## 8. 今回の確認記録

- 反映コミット：`e17dd7a085c484c216fac3076c407e0ba0540438`
- [変更PR #11](https://github.com/IKEGAMI-99/jinkaku/pull/11)
- [検証用ビルド成功](https://github.com/IKEGAMI-99/jinkaku/actions/runs/34412410120)
- [メインの配布用ビルド成功](https://github.com/IKEGAMI-99/jinkaku/actions/runs/34413155128)
- [v0.1.53 Release](https://github.com/IKEGAMI-99/jinkaku/releases/tag/v0.1.53)
- 検証用artifactのZIPとAPKのCRC確認が成功。
- 検証用APK内のヘッダーPNGは1536×512で、可視部分のRGBとアルファが作成したPNGと一致。
- メイン反映後のソースツリーは検証したソースツリーと一致。
- 公開された `version.json` のSHA-256が、上記バージョン情報の内容と一致。
- 実機での起動・推論テストは未実施。
