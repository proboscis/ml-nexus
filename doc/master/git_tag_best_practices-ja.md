# Git タグのベストプラクティス for ml-nexus

このドキュメントでは、`ml-nexus`ライブラリの開発におけるGitタグの使用に関するベストプラクティスを概説します。

## 目次

1. [セマンティックバージョニングとGitタグ](#セマンティックバージョニングとgitタグ)
2. [タグを作成するタイミング](#タグを作成するタイミング)
3. [タグ作成プロセス](#タグ作成プロセス)
4. [タグコンテンツのベストプラクティス](#タグコンテンツのベストプラクティス)
5. [リリースワークフローの統合](#リリースワークフローの統合)
6. [自動化オプション](#自動化オプション)
7. [タグ管理](#タグ管理)
8. [GitHubワークフロー例](#githubワークフロー例)
9. [Gitタグと依存関係管理](#gitタグと依存関係管理)

## セマンティックバージョニングとGitタグ

Gitタグは[セマンティックバージョニング](https://semver.org/)（SemVer）の原則に従うべきです：

- 形式：`MAJOR.MINOR.PATCH`を使用
  - **MAJOR**：互換性のないAPIの変更時にインクリメント
  - **MINOR**：後方互換性のある新機能追加時にインクリメント
  - **PATCH**：後方互換性のあるバグ修正時にインクリメント

- 明確にするために、タグの前に「v」を付ける（例：`v0.1.7`）
- プレリリースバージョンには、`-alpha.1`、`-beta.2`、`-rc.1`などのサフィックスを使用可能

## タグを作成するタイミング

- ライブラリの公開リリースごとにタグを作成
- 安定した、テスト済みのコミットにのみタグを付ける
- 機能ブランチではなく、main/masterブランチにマージした後にタグを作成
- PyPIに公開する直前または直後にタグを付ける
- ユーザーが参照したい重要なプレリリースにもタグを作成することを検討

## タグ作成プロセス

```bash
# 正しいコミットにいることを確認
git checkout main
git pull

# 注釈付きタグを作成（軽量タグよりも推奨）
git tag -a v0.1.7 -m "Release v0.1.7: 機能Xを追加し、バグYを修正"

# タグをリモートにプッシュ
git push origin v0.1.7

# すべてのタグをプッシュ（代替方法）
git push --tags
```

## タグコンテンツのベストプラクティス

- 軽量タグではなく、メタデータを含む注釈付きタグ（`-a`フラグ）を使用
- リリースの主要な変更点を説明する意味のあるメッセージを書く
- トレーサビリティのために、タグメッセージ内でissue/PR番号を参照
- 破壊的変更に対する移行ノートを含めることを検討
- メッセージは簡潔だが情報量が多いものにする

良いタグメッセージの例：
```
Release v0.1.7

- pinjectedの依存関係を更新 (#123)
- 並行リクエストのレート制限問題を修正 (#125)
- APIタイムアウトのエラーハンドリングを改善
```

## リリースワークフローの統合

1. `pyproject.toml`のバージョンを更新（例：0.1.6a20 → 0.1.7）
2. 変更履歴を管理している場合は更新
3. 「バージョンを0.1.7に更新」などのメッセージでこれらの変更をコミット
4. バージョンに一致するGitタグを作成してプッシュ
5. パッケージをビルドしてPyPIに公開

ワークフロー例：
```bash
# pyproject.tomlと変更履歴を更新
# 変更をコミット
git add pyproject.toml CHANGELOG.md
git commit -m "バージョンを0.1.7に更新"

# タグを作成してプッシュ
git tag -a v0.1.7 -m "Release v0.1.7: 機能Xを追加し、バグYを修正"
git push origin main
git push origin v0.1.7

# ビルドして公開
python -m build
twine upload dist/*
```

## 自動化オプション

- GitHub ActionsなどのCI/CDを使用して：
  - コードとタグ間のバージョン一致を検証
  - タグ作成前にテストを実行
  - タグがプッシュされたときに自動的にPyPIに公開
  - コミットからリリースノートを生成
  - タグから自動的にGitHubリリースを作成

- [bump2version](https://github.com/c4urself/bump2version)などのツールを使用してバージョン更新を自動化することを検討

## タグ管理

- 公開されたタグは削除や移動をしない
- 間違いがあった場合は、既存のタグを修正するのではなく、新しいタグを作成
- プレリリースにはリリース候補を使用：`v1.0.0-rc.1`
- チーム向けにタグの命名規則を文書化
- プッシュされなかったローカルタグを定期的にクリーンアップ

## GitHubワークフロー例

このGitHub Actionsワークフローは、タグがプッシュされたときに自動的にパッケージをビルドしてPyPIに公開します：

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: ${{ secrets.PYPI_USERNAME }}
          TWINE_PASSWORD: ${{ secrets.PYPI_PASSWORD }}
        run: twine upload dist/*
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

## Gitタグと依存関係管理

### 他のプロジェクトで特定のGitタグに依存する

他のプロジェクトがGit（PyPIではなく）から直接このライブラリの特定バージョンに依存する必要がある場合、特定のタグを参照できます。これは、開発中や、まだPyPIに公開されていない機能が必要な場合に特に便利です。

#### Ryeとpyproject.tomlの使用

Ryeを使用するプロジェクトで、このライブラリの特定のGitタグに依存するには、プロジェクトの`pyproject.toml`に以下を追加します：

```toml
[project]
# ... その他のプロジェクト設定 ...
dependencies = [
    # ... その他の依存関係 ...
    "ml-nexus @ git+https://github.com/proboscis/ml-nexus.git@v0.1.7",
]
```

特定のコミットやブランチを指定することもできます：

```toml
# 特定のコミットに依存
"ml-nexus @ git+https://github.com/proboscis/ml-nexus.git@5ad6099",

# ブランチに依存
"ml-nexus @ git+https://github.com/proboscis/ml-nexus.git@main",
```

#### Poetryの使用

Ryeの代わりにPoetryを使用する場合、構文は似ています：

```toml
[tool.poetry.dependencies]
ml-nexus = {git = "https://github.com/proboscis/ml-nexus.git", tag = "v0.1.7"}
```

#### pipの使用

pipを使用すると、Gitタグから直接インストールできます：

```bash
pip install git+https://github.com/proboscis/ml-nexus.git@v0.1.7
```

### タグ付きバージョンを使用する利点

- **安定性**：特定のタグに依存することで、安定したテスト済みのバージョンを確保
- **再現性**：正確なコードバージョンが固定されているため、ビルドは再現可能
- **柔軟性**：タグ参照を変更するだけで、バージョン間の切り替えが容易
- **プレリリースアクセス**：PyPIに公開される前に新機能にアクセス可能

---

これらのプラクティスに従うことで、明確なバージョン履歴を維持し、ユーザーにとってリリースをより予測可能にし、開発ワークフローを効率化できます。