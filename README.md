# ml-nexus

ML Nexusは、機械学習プロジェクトの構造と依存関係を定義するためのライブラリです。

## 概要

このライブラリは、`pinjected`依存性注入ライブラリを活用して、機械学習プロジェクトの構造化と依存関係の管理を容易にします。

## ドキュメント

- [Gitタグのベストプラクティス](doc/master/git_tag_best_practices-ja.md) ([English](doc/translations/en/git_tag_best_practices-en.md))

## インストール

```bash
pip install ml-nexus
```

または、特定のバージョンを指定してインストール：

```bash
pip install git+https://github.com/proboscis/ml-nexus.git@v0.1.6a20
```

## 使用例

```python
from ml_nexus import IdPath
from pinjected import injected

@injected
def example_function(IdPath, /):
    # リソースファイルのパスを取得
    path = IdPath("example_resource")
    return path
```

## ライセンス

このプロジェクトは、[ライセンス名]の下でライセンスされています。