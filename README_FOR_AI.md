# Pinjected: AIのための利用ガイド

このドキュメントは、Pythonの依存性注入（Dependency Injection）ライブラリ「Pinjected」をAIが効果的に利用するための情報をまとめたものです。

## 1. Pinjectedの概要

Pinjectedは、研究開発向けに設計されたPythonのDependency Injection（DI）ライブラリです。従来の設定管理やコード構造の問題（巨大なcfgオブジェクト依存、if分岐の氾濫、テスト困難性など）を解決するために開発されました。

### 1.1 主な特徴

- **直感的な依存定義**: `@instance`や`@injected`デコレータを使用したPythonicな依存関係の定義
- **key-valueスタイルの依存合成**: `design()`関数による簡潔な依存関係の組み立て
- **CLIからの柔軟なパラメータ上書き**: 実行時にコマンドラインから依存関係やパラメータを変更可能
- **複数エントリーポイントの容易な管理**: 同一ファイル内に複数の実行可能なInjectedオブジェクトを定義可能
- **IDE統合**: VSCodeやPyCharm用のプラグインによる開発支援

### 1.2 従来手法との比較

従来のOmegaConfやHydraなどの設定管理ツールでは、以下のような問題がありました：

- cfgオブジェクトへの全体依存
- 分岐処理の氾濫
- 単体テストや部分的デバッグの難しさ
- God class問題と拡張性の限界

Pinjectedはこれらの問題を解決し、より柔軟で再利用性の高いコード構造を実現します。

## 2. 基本機能

### 2.1 @instanceデコレータ

`@instance`デコレータは、依存解決における「オブジェクト提供者（プロバイダ）」を定義します。関数の引数はすべて依存パラメータとして扱われ、戻り値がインスタンスとして提供されます。

```python
from pinjected import instance

# モデル定義の例
@instance
def model__simplecnn(input_size, hidden_units):
    return SimpleCNN(input_size=input_size, hidden_units=hidden_units)

# データセット定義の例
@instance
def dataset__mnist(batch_size):
    return MNISTDataset(batch_size=batch_size)
```

### 2.2 @injectedデコレータ

`@injected`デコレータは、関数引数を「注入対象の引数」と「呼び出し時に指定する引数」に分離できます。`/`の左側が依存として注入され、右側が実行時に渡される引数です。

```python
from pinjected import injected

@injected
def generate_text(llm_model, /, prompt: str):
    # llm_modelはDIから注入される
    # promptは実行時に任意の値を渡せる
    return llm_model.generate(prompt)
```

### 2.3 design()関数

`design()`関数は、key=value形式で依存オブジェクトやパラメータをまとめる「設計図」を作成します。`+`演算子で複数のdesignを合成できます。

```python
from pinjected import design

# 基本設計
base_design = design(
    learning_rate=0.001,
    batch_size=128,
    image_size=32
)

# モデル固有の設計
mnist_design = base_design + design(
    model=model__simplecnn,
    dataset=dataset__mnist,
    trainer=Trainer
)
```

### 2.4 __meta_design__

`__meta_design__`は、Pinjectedが自動的に収集する特別なグローバル変数です。CLIから実行する際のデフォルトのデザインを指定できます。

```python
__meta_design__ = design(
    overrides=mnist_design  # CLIで指定しなかったときに利用されるデザイン
)
```

## 3. 実行方法とCLIオプション

### 3.1 基本的な実行方法

Pinjectedは、`python -m pinjected run <path.to.target>`の形式で実行します。

```bash
# run_trainを実行する例
python -m pinjected run example.run_train
```

### 3.2 パラメータ上書き

`--`オプションを用いて、個別のパラメータや依存項目を指定してdesignを上書きできます。

```bash
# batch_sizeとlearning_rateを上書きする例
python -m pinjected run example.run_train --batch_size=64 --learning_rate=0.0001
```

### 3.3 依存オブジェクトの差し替え

`{}`で囲んだパスを指定することで、依存オブジェクトを差し替えられます。

```bash
# modelとdatasetを差し替える例
python -m pinjected run example.run_train --model='{example.model__another}' --dataset='{example.dataset__cifar10}'
```

### 3.4 overridesによるデザイン切り替え

`--overrides`オプションで、事前に定義したデザインを指定できます。

```bash
# mnist_designを使って実行する例
python -m pinjected run example.run_train --overrides={example.mnist_design}
```

## 4. 高度な機能

### 4.1 ~/.pinjected.pyによるユーザーローカル設定

`~/.pinjected.py`ファイルを通じて、ユーザーローカルなデザインを定義・注入できます。APIキーやローカルパスなど、ユーザーごとに異なる機密情報やパス設定を管理するのに適しています。

```python
# ~/.pinjected.py
from pinjected import design

default_design = design(
    openai_api_key = "sk-xxxxxx_your_secret_key_here",
    cache_dir = "/home/user/.cache/myproject"
)
```

### 4.2 withステートメントによるデザインオーバーライド

`with`ステートメントを用いて、一時的なオーバーライドを行えます。

```python
from pinjected import providers, IProxy, design

with design(
    batch_size=64  # 一時的にbatch_sizeを64へ
):
    # このwithブロック内ではbatch_sizeは64として解決される
    train_with_bs_64: IProxy = train()
```

### 4.3 InjectedとIProxy

#### 4.3.1 基本概念

- **Injected**: 「未解決の依存」を表すオブジェクト
- **IProxy**: Python的なDSLでInjectedを操るためのプロキシクラス

```python
from pinjected import Injected

a = Injected.by_name('a')  # 'a'という名前の依存値を表すInjectedオブジェクト
b = Injected.by_name('b')

# IProxy化して算術演算
a_proxy = a.proxy
b_proxy = b.proxy
sum_proxy = a_proxy + b_proxy
```

#### 4.3.2 map/zipによる関数的合成

```python
# mapによる変換
a_plus_one = a.map(lambda x: x + 1)

# zipによる複数依存値の結合
ab_tuple = Injected.zip(a, b)  # (resolved_a, resolved_b)のタプル
```

#### 4.3.3 Injected.dict()とInjected.list()

```python
# 辞書形式でまとめる
my_dict = Injected.dict(
    learning_rate=Injected.by_name("learning_rate"),
    batch_size=Injected.by_name("batch_size")
)

# リスト形式でまとめる
my_list = Injected.list(
    Injected.by_name("model"),
    Injected.by_name("dataset"),
    Injected.by_name("optimizer")
)
```

#### 4.3.4 injected()関数

`injected()`関数は`Injected.by_name().proxy`の短縮形で、依存名から直接IProxyオブジェクトを取得するための便利な関数です。

```python
from pinjected import injected

# 以下は等価です
a_proxy = Injected.by_name("a").proxy
a_proxy = injected("a")
```

#### 4.3.4 DSL的表記

```python
# パス操作
cache_subdir = injected("cache_dir") / "subdir" / "data.pkl"

# インデックスアクセス
train_sample_0 = injected("dataset")["train"][0]
```

## 5. ユースケース例

### 5.1 モデルロードと実行時パラメータ

大規模言語モデル（LLM）や拡散モデル（Stable Diffusion）のような巨大なモデルを扱う場合、モデルは一度ロードして再利用し、入出力パラメータは都度変更したいケースが多いです。

```python
@instance
def llm_client(openai_api_key):
    openai.api_key = openai_api_key
    return openai.ChatCompletion

@injected
def generate_text(llm_client, /, prompt: str):
    # llm_clientはDIで注入
    # promptは実行時に指定するパラメータ
    response = llm_client.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message["content"]
```

### 5.2 キャッシュパスや外部リソースパスの管理

環境によって異なるリソースパスを柔軟に扱えます。

```python
@instance
def cache_dir():
    # ~/.pinjected.py でこの値を上書き可能
    return Path("/tmp/myproject_cache")

@instance
def embeddings_cache_path(cache_dir):
    # cache_dirが変われば自動的に変わる
    return cache_dir / "embeddings.pkl"
```

### 5.3 設定バリエーション生成と再利用

ハイパーパラメータ探索や条件分岐的な実験を数多く試す場合に便利です。

```python
# 基本設計
base_design = design(
    learning_rate=0.001,
    batch_size=128,
    model_identifier="model_base"
)

# 学習率バリエーション
conf_lr_001 = base_design + design(learning_rate=0.001)
conf_lr_01 = base_design + design(learning_rate=0.01)
conf_lr_1 = base_design + design(learning_rate=0.1)

# モデルバリエーション
model_resnet = design(model=model__resnet)
model_transformer = design(model=model__transformer)

# 組み合わせ
conf_lr_001_resnet = conf_lr_001 + model_resnet
conf_lr_001_transformer = conf_lr_001 + model_transformer
```

## 6. IDEサポート

### 6.1 VSCode/PyCharmプラグイン

- **ワンクリック実行**: `@injected`/`@instance`デコレータ付き関数や`IProxy`型アノテーション付き変数をワンクリックで実行可能
- **依存関係可視化**: 依存グラフをブラウザで視覚的に表示

### 6.2 実行例

```python
# IProxyアノテーションを付けると実行ボタンが表示される
check_dataset: IProxy = injected('dataset')[0]
```

## 7. 実装パターンとベストプラクティス

### 7.1 テスト用IProxyオブジェクト

実装関数と同じファイル内にテスト用のIProxyオブジェクトを配置するパターンが一般的です。

```python
@injected
def process_data(dataset, /, filter_condition=None):
    # データ処理ロジック
    return processed_data

# テスト用IProxyオブジェクト
test_process_data: IProxy = process_data(filter_condition="test")
```

このIProxyオブジェクトは以下のコマンドで実行できます：

```bash
python -m pinjected run your_module.test_process_data
```

### 7.2 依存関係の命名規則

依存関係の命名には、衝突を避けるために以下のようなパターンが推奨されます：

- モジュール名やカテゴリを接頭辞として使用: `model__resnet`, `dataset__mnist`
- ライブラリ用途では、パッケージ名を含める: `my_package__module__param1`

### 7.3 設計上の考慮事項

- **依存キーの衝突を避ける**: 同じ名前のキーが別の箇所で定義されないよう注意
- **適切な粒度で依存を分割**: 大きすぎる依存は再利用性を下げる
- **テスト容易性を考慮**: 単体テストや部分実行がしやすいよう設計

## 8. 注意点と制限事項

### 8.1 学習コストと開発体制への影響

- チームメンバーがDIやDSL的な記法に慣れる必要がある
- 共通理解の確立が重要

### 8.2 デバッグやエラー追跡

- 依存解決が遅延されるため、エラー発生タイミングの把握が難しい場合がある
- スタックトレースが複雑になることがある

### 8.3 メンテナンス性とスケール

- 大規模プロジェクトでは依存キーの管理が複雑になる可能性
- バリエーション管理が膨大になる場合がある

## 9. まとめ

Pinjectedは、研究開発現場の実験コードが抱える課題（巨大なcfg依存や膨大なif分岐、部分的テストの難しさなど）に対する効果的な解決策です。

主なメリット:

- **設定管理の柔軟性**: design()による依存定義とCLIオプション、~/.pinjected.pyによるローカル設定上書き
- **if分岐の削減と可読性向上**: @instanceや@injectedを使った明示的なオブジェクト注入
- **部分テスト・デバッグの容易化**: 特定コンポーネントの単独実行・確認
- **高度なDSL的表現**: Injected/IProxyを用いた宣言的かつ直感的な記述

これらの特徴により、研究開発の反復速度が向上し、拡張や再利用も容易になります。