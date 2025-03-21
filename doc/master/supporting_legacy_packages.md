# ビルド時に特定の前提を要求するパッケージへの対応

## 概要

basicsr などのレガシーライブラリがビルド時に torch などの特定の依存関係を要求する場合に、UVで適切に処理するための解決策です。

## 問題点

一部のレガシーパッケージ（basicsr など）は、ビルド時に特定の依存関係（torch など）を必要とします。UVの標準的なアプローチではこれらのパッケージのインストールに問題が発生することがあります。

## 解決策

### 1. プロジェクトの依存関係を分離する

`pyproject.toml`で依存関係を適切に分離します:

```toml
[project.optional-dependencies]
build = [
  "torch==2.3.0",
  "cython",
  "numpy>=1.17"
]
basicsr = [
  "basicsr==1.3.5"
]
[tool.uv]
no-build-isolation-package = ["basicsr"]
```

### 2. schematicsのinit_scriptをカスタマイズする

`a_map_scripts`メソッドを使用して、スクリプトを動的に変更します:

```python
schematic = schematic_universal(project)
@injected
async def a_hack_uv_sync_with_torch_dep_package(lines: list[str]) -> list[str]:
    # This hack works!
    res = []
    for line in lines:
        if 'uv sync' in line:
            res += [
                "uv sync --extra build",
                "uv sync --extra build --extra basicsr"
            ]
        else:
            res.append(line)
    return res
hacked_schematics = schematic.a_map_scripts(a_hack_uv_sync_with_torch_dep_package).await__()
```

この方法により、標準の`uv sync`コマンドをオプションの依存関係を含めた複数のコマンドに置き換えることができます。

## 実装状況

* `pinjected`の依存関係が0.2.245にアップデートされました
* `ContainerSchematic`クラスに`a_map_scripts`メソッドが追加されました
* テスト用の実装が`test_schematics_for_uv_with_accelerator.py`に追加されました

## 今後の対応

このアプローチを標準化して、特定のパッケージタイプに対して自動的に適用できるよう検討することが推奨されます。