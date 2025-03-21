
# 問題

- 現状、dockerホストにsshしてdocker コマンドを打つような実装になっている。
- 様々な方法でDockerを利用する可能性があるので、ここを抽象化しておく必要がある。
- 少なくとも、Local DockerもしくはRemote Dockerで実装を入れ替えられるようにしたい

# TODO 
- どこでどのようにDocker機能が用いられているかを検索し、変更可能性を検討、適当な抽象化を定める
- interfaceを策定する

# 現状の実装分析

現在のDocker関連の実装を分析した結果、以下のクラスが主要な役割を担っています：

1. `DockerHostEnvironment` (`src/ml_nexus/docker_env.py`)
   - 基本的なDockerコンテナ実行環境
   - SSHを使用してリモートのDockerホストにコマンドを送信
   - `docker run`でコンテナを起動し、スクリプト実行後にコンテナを破棄

2. `DockerEnvFromSchematics` (`src/ml_nexus/docker/builder/docker_env_with_schematics.py`)
   - `ContainerSchematic`を使用して`DockerHostEnvironment`を設定するラッパー
   - マウントの準備などを担当

3. `PersistentDockerEnvFromSchematics` (`src/ml_nexus/docker/builder/persistent.py`)
   - 永続的なDockerコンテナを管理するクラス
   - `DockerEnvFromSchematics`を使用してコンテナを作成
   - `docker exec`でスクリプトを実行
   - 一部のコードがローカルDockerを直接使用するように書かれている

現状の問題点：
- Dockerとの通信方法（SSHを使用したリモートDockerホスト、ローカルDocker）が抽象化されていない
- `DockerHostEnvironment`はSSHを前提としており、ローカルDockerに対応していない
- `PersistentDockerEnvFromSchematics`は一部のメソッドでローカルDockerを使用しているが、`docker_host`パラメータも持っている

# 提案する抽象化

## 1. DockerClientインターフェース

Dockerとの通信方法を抽象化するインターフェースを作成します：

```python
class DockerClient(ABC):
    """
    Dockerとの通信を抽象化するインターフェース。
    Local DockerとRemote Dockerの両方に対応できるようにする。
    """

    @abstractmethod
    async def run_container(self, image: str, command: str, options: List[str] = None) -> str:
        """コンテナを実行する"""
        pass

    @abstractmethod
    async def exec_container(self, container: str, command: str) -> str:
        """実行中のコンテナ内でコマンドを実行する"""
        pass

    @abstractmethod
    async def build_image(self, context_dir: Path, tag: str, options: List[str] = None) -> str:
        """イメージをビルドする"""
        pass

    # その他必要なメソッド...
```

## 2. DockerClientの実装

このインターフェースを実装する具体的なクラスを作成します：

1. `LocalDockerClient` - ローカルのDockerデーモンと通信するクライアント
2. `RemoteDockerClient` - SSHを使用してリモートのDockerホストと通信するクライアント

## 3. デフォルトDockerClientの提供

Pinjectedの設計パターンに従い、デフォルトのDockerClientを提供します：

```python
@instance
def ml_nexus_default_docker_client(
    a_system,
    logger,
    ml_nexus_docker_host: Optional[str] = None
) -> DockerClient:
    """デフォルトのDockerClient"""
    if ml_nexus_docker_host is None or ml_nexus_docker_host == "localhost":
        return LocalDockerClient(_a_system=a_system, _logger=logger)
    else:
        return RemoteDockerClient(_a_system=a_system, _logger=logger, host=ml_nexus_docker_host)
```

## 4. 既存クラスの修正

既存のクラスを修正して、`docker_host`引数を削除し、代わりに`docker_client`を注入または引数で設定できるようにします：

1. `DockerHostEnvironment` - `docker_host`引数を削除し、`docker_client`を注入
2. `DockerEnvFromSchematics` - `docker_host`引数を削除し、`docker_client`を注入
3. `PersistentDockerEnvFromSchematics` - `docker_host`引数を削除し、`docker_client`を注入

例えば、`DockerHostEnvironment`の修正例：

```python
@dataclass
class DockerHostEnvironment(IScriptRunner):
    # ...
    _ml_nexus_default_docker_client: DockerClient
    
    project: ProjectDef
    docker_builder: DockerBuilder
    docker_client: Optional[DockerClient] = None
    
    # ...
    
    def __post_init__(self):
        # ...
        if self.docker_client is None:
            self.docker_client = self._ml_nexus_default_docker_client
        # ...
```

この抽象化により、Local DockerとRemote Dockerの実装を簡単に入れ替えられるようになります。また、将来的に新しいDocker実装（例：Docker APIを直接使用する実装）を追加することも容易になります。

# 詳細な分析と実装方針

## 現在の実装の詳細分析

コードを詳細に分析した結果、以下の点が明らかになりました：

1. `DockerHostEnvironment`クラス
   - `docker_host`パラメータを持ち、SSHを使用してリモートホストにコマンドを送信
   - `upload_remote`、`delete_remote`、`download_remote`メソッドはリモートホストとの間でファイルを転送
   - `prepare`メソッドは`mounter.prepare_resource`を呼び出してリソースを準備

2. `DockerEnvFromSchematics`クラス
   - `docker_host`パラメータを持ち、`DockerHostEnvironment`に渡す
   - `_mkdir`、`_rsync_mount`メソッドはSSHを使用してリモートホストにコマンドを送信

3. `PersistentDockerEnvFromSchematics`クラス
   - `docker_host`パラメータを持つが、一部のメソッドではローカルDockerを直接使用
   - `upload`、`download`、`delete`メソッドは`docker cp`コマンドを使用

## 実装上の課題

1. **リモート前提の設計**: 現在の実装はリモートホストでの操作を前提としており、ローカルDockerに対応させるには注意が必要
2. **ファイル転送の抽象化**: `upload_remote`などのメソッドはリモートホストとの間でファイルを転送するために使用されており、ローカルDockerでは異なる実装が必要
3. **リソース準備の抽象化**: `prepare_resource`メソッドはリモートホストにリソースを準備するために使用されており、ローカルDockerでは異なる実装が必要

## 段階的な実装方針

抽象化を安全に進めるために、以下の段階的なアプローチを提案します：

### フェーズ1: DockerClientインターフェースの作成

1. `DockerClient`インターフェースを作成し、基本的なDockerコマンド（run、exec、build、pushなど）を抽象化
2. `LocalDockerClient`と`RemoteDockerClient`の実装を提供
3. `ml_nexus_default_docker_client`をデフォルトのDockerクライアントとして提供

### フェーズ2: DockerHostEnvironmentの修正（最小限の変更）

1. `DockerHostEnvironment`クラスに`docker_client`パラメータを追加（`docker_host`は残す）
2. `run_script`、`run_script_without_init`メソッドを修正して、`docker_client`が提供されている場合はそれを使用
3. 他のメソッドは現状のまま維持

### フェーズ3: DockerEnvFromSchematicsの修正

1. `DockerEnvFromSchematics`クラスに`docker_client`パラメータを追加（`docker_host`は残す）
2. `_new_env`メソッドを修正して、`docker_client`が提供されている場合はそれを`DockerHostEnvironment`に渡す

### フェーズ4: PersistentDockerEnvFromSchematicsの修正

1. `PersistentDockerEnvFromSchematics`クラスに`docker_client`パラメータを追加（`docker_host`は残す）
2. `ensure_container`、`run_script`、`stop`などのメソッドを修正して、`docker_client`が提供されている場合はそれを使用

### フェーズ5: 完全な抽象化（将来的な対応）

1. `docker_host`パラメータを削除し、完全に`docker_client`に移行
2. ファイル転送やリソース準備の抽象化を`DockerClient`インターフェースに追加
3. すべてのクラスを修正して、新しい抽象化を使用するようにする
