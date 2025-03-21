import asyncio
import base64
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

import pandas as pd
from pinjected import injected, instance


class DockerClient(ABC):
    """
    Dockerとの通信を抽象化するインターフェース。
    Local DockerとRemote Dockerの両方に対応できるようにする。
    """

    @abstractmethod
    async def run_container(self, image: str, command: str, options: List[str] = None) -> str:
        """
        Dockerコンテナを実行する
        
        Args:
            image: 実行するDockerイメージ
            command: コンテナ内で実行するコマンド
            options: docker runに渡すオプション
            
        Returns:
            コマンドの実行結果
        """
        pass

    @abstractmethod
    async def exec_container(self, container: str, command: str) -> str:
        """
        実行中のコンテナ内でコマンドを実行する
        
        Args:
            container: コンテナ名またはID
            command: 実行するコマンド
            
        Returns:
            コマンドの実行結果
        """
        pass

    @abstractmethod
    async def build_image(self, context_dir: Path, tag: str, options: List[str] = None) -> str:
        """
        Dockerイメージをビルドする
        
        Args:
            context_dir: ビルドコンテキストのディレクトリ
            tag: イメージのタグ
            options: docker buildに渡すオプション
            
        Returns:
            ビルドしたイメージのタグ
        """
        pass

    @abstractmethod
    async def push_image(self, tag: str) -> None:
        """
        Dockerイメージをレジストリにプッシュする
        
        Args:
            tag: プッシュするイメージのタグ
        """
        pass

    @abstractmethod
    async def copy_to_container(self, src: Path, container: str, dst: Path) -> None:
        """
        ファイルをコンテナにコピーする
        
        Args:
            src: コピー元のパス
            container: コンテナ名またはID
            dst: コンテナ内のコピー先パス
        """
        pass

    @abstractmethod
    async def copy_from_container(self, container: str, src: Path, dst: Path) -> None:
        """
        ファイルをコンテナからコピーする
        
        Args:
            container: コンテナ名またはID
            src: コンテナ内のコピー元パス
            dst: コピー先のパス
        """
        pass

    @abstractmethod
    async def stop_container(self, container: str) -> None:
        """
        コンテナを停止する
        
        Args:
            container: 停止するコンテナの名前またはID
        """
        pass

    @abstractmethod
    async def list_containers(self) -> Dict[str, Any]:
        """
        実行中のコンテナの一覧を取得する
        
        Returns:
            コンテナ情報の辞書
        """
        pass

    @abstractmethod
    async def container_exists(self, container: str) -> bool:
        """
        指定した名前のコンテナが存在するかどうかを確認する
        
        Args:
            container: コンテナ名
            
        Returns:
            コンテナが存在する場合はTrue、そうでない場合はFalse
        """
        pass

    @abstractmethod
    async def container_is_running(self, container: str) -> bool:
        """
        指定した名前のコンテナが実行中かどうかを確認する
        
        Args:
            container: コンテナ名
            
        Returns:
            コンテナが実行中の場合はTrue、そうでない場合はFalse
        """
        pass

    @abstractmethod
    async def mkdir_in_container(self, container: str, path: Path) -> None:
        """
        コンテナ内にディレクトリを作成する
        
        Args:
            container: コンテナ名またはID
            path: 作成するディレクトリのパス
        """
        pass


@dataclass
class LocalDockerClient(DockerClient):
    """
    ローカルのDockerデーモンと通信するクライアント
    """
    _a_system: callable
    _logger: Any

    async def run_container(self, image: str, command: str, options: List[str] = None) -> str:
        options_str = " ".join(options) if options else ""
        cmd = f"docker run {options_str} {image} {command}"
        return await self._a_system(cmd)

    async def exec_container(self, container: str, command: str) -> str:
        cmd = f"docker exec {container} {command}"
        return await self._a_system(cmd)

    async def build_image(self, context_dir: Path, tag: str, options: List[str] = None) -> str:
        options_str = " ".join(options) if options else ""
        cmd = f"docker build {options_str} -t {tag} {context_dir}"
        await self._a_system(cmd)
        return tag

    async def push_image(self, tag: str) -> None:
        await self._a_system(f"docker push {tag}")

    async def copy_to_container(self, src: Path, container: str, dst: Path) -> None:
        await self._a_system(f"docker cp {src} {container}:{dst}")

    async def copy_from_container(self, container: str, src: Path, dst: Path) -> None:
        await self._a_system(f"docker cp {container}:{src} {dst}")

    async def stop_container(self, container: str) -> None:
        await self._a_system(f"docker stop {container}")

    async def list_containers(self) -> Dict[str, Any]:
        ps = await asyncio.subprocess.create_subprocess_shell(
            "docker ps -a --format '{{json .}}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ps.communicate()
        
        data = [json.loads(line.strip()) for line in stdout.decode().split("\n") if line.strip()]
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index("Names", inplace=True)
            return df.to_dict(orient="index")
        return {}

    async def container_exists(self, container: str) -> bool:
        containers = await self.list_containers()
        return container in containers

    async def container_is_running(self, container: str) -> bool:
        containers = await self.list_containers()
        if container in containers:
            return containers[container]["State"] == "running"
        return False

    async def mkdir_in_container(self, container: str, path: Path) -> None:
        await self.exec_container(container, f"mkdir -p {path}")


@dataclass
class RemoteDockerClient(DockerClient):
    """
    リモートのDockerホストと通信するクライアント
    """
    _a_system: callable
    _logger: Any
    
    host: str

    async def run_container(self, image: str, command: str, options: List[str] = None) -> str:
        options_str = " ".join(options) if options else ""
        cmd = f"ssh {self.host} \"docker run {options_str} {image} {command}\""
        return await self._a_system(cmd)

    async def exec_container(self, container: str, command: str) -> str:
        cmd = f"ssh {self.host} \"docker exec {container} {command}\""
        return await self._a_system(cmd)

    async def build_image(self, context_dir: Path, tag: str, options: List[str] = None) -> str:
        options_str = " ".join(options) if options else ""
        cmd = f"ssh {self.host} \"docker build {options_str} -t {tag} {context_dir}\""
        await self._a_system(cmd)
        return tag

    async def push_image(self, tag: str) -> None:
        await self._a_system(f"ssh {self.host} \"docker push {tag}\"")

    async def copy_to_container(self, src: Path, container: str, dst: Path) -> None:
        # ローカルファイルをリモートホストに転送してからコンテナにコピー
        remote_tmp = f"/tmp/{src.name}"
        await self._a_system(f"scp {src} {self.host}:{remote_tmp}")
        await self._a_system(f"ssh {self.host} \"docker cp {remote_tmp} {container}:{dst}\"")
        await self._a_system(f"ssh {self.host} \"rm {remote_tmp}\"")

    async def copy_from_container(self, container: str, src: Path, dst: Path) -> None:
        # コンテナからリモートホストにコピーしてからローカルに転送
        remote_tmp = f"/tmp/{src.name}"
        await self._a_system(f"ssh {self.host} \"docker cp {container}:{src} {remote_tmp}\"")
        await self._a_system(f"scp {self.host}:{remote_tmp} {dst}")
        await self._a_system(f"ssh {self.host} \"rm {remote_tmp}\"")

    async def stop_container(self, container: str) -> None:
        await self._a_system(f"ssh {self.host} \"docker stop {container}\"")

    async def list_containers(self) -> Dict[str, Any]:
        ps = await asyncio.subprocess.create_subprocess_shell(
            f"ssh {self.host} \"docker ps -a --format '{{{{json .}}}}'\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ps.communicate()
        
        data = [json.loads(line.strip()) for line in stdout.decode().split("\n") if line.strip()]
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index("Names", inplace=True)
            return df.to_dict(orient="index")
        return {}

    async def container_exists(self, container: str) -> bool:
        containers = await self.list_containers()
        return container in containers

    async def container_is_running(self, container: str) -> bool:
        containers = await self.list_containers()
        if container in containers:
            return containers[container]["State"] == "running"
        return False

    async def mkdir_in_container(self, container: str, path: Path) -> None:
        await self.exec_container(container, f"mkdir -p {path}")


@instance
def ml_nexus_default_docker_client(
    a_system,
    logger,
    ml_nexus_docker_host: Optional[str] = None
) -> DockerClient:
    """
    デフォルトのDockerClient
    
    Args:
        ml_nexus_docker_host: Dockerホスト。Noneの場合はローカルDockerを使用
        
    Returns:
        DockerClient実装
    """
    if ml_nexus_docker_host is None or ml_nexus_docker_host == "localhost" or ml_nexus_docker_host == "127.0.0.1":
        return LocalDockerClient(_a_system=a_system, _logger=logger)
    else:
        return RemoteDockerClient(_a_system=a_system, _logger=logger, host=ml_nexus_docker_host)


# テスト用のIProxy
test_local_docker_client: Any = injected(ml_nexus_default_docker_client)(ml_nexus_docker_host=None)
test_remote_docker_client: Any = injected(ml_nexus_default_docker_client)(ml_nexus_docker_host="example.com")