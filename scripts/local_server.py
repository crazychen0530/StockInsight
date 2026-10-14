"""Start existing local services and an explicitly requested anonymous read-only preview.

Never initializes databases, rebuilds existing containers, installs system software or
prints credentials. Public preview owns a separate ephemeral proxy and an 8-hour tunnel.
"""

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data/runtime"
BINARY = ROOT / "data/tools/cloudflared-2026.10.0"
DIGEST = "d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db"
PROJECT = "stockinsight-m6"


def docker(*args, quiet=False):
    result = subprocess.run(
        ["docker", *args], text=True, capture_output=True, check=False
    )
    if result.returncode:
        # Docker errors can include environment/config text; never echo arbitrary output.
        raise RuntimeError("Docker操作失败。请检查Docker是否运行及当前用户权限。")
    if not quiet and result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    return result.stdout


def inspect(name):
    return json.loads(docker("inspect", name, quiet=True))[0]


def start():
    for service in ("db", "api", "proxy", "scheduler", "backup", "monitor"):
        name = f"{PROJECT}-{service}-1"
        item = inspect(name)
        if item["Config"]["Labels"].get("com.docker.compose.project") != PROJECT:
            raise RuntimeError("容器项目不匹配，拒绝启动。")
        if not item["State"]["Running"]:
            docker("start", name)
    deadline = time.monotonic() + 120
    for service in ("db", "api"):
        while True:
            item = inspect(f"{PROJECT}-{service}-1")
            if item["State"].get("Health", {}).get("Status") == "healthy":
                break
            if time.monotonic() > deadline or not item["State"]["Running"]:
                raise RuntimeError("业务服务尚未健康，拒绝开放公网。")
            print(f"等待 {service} 健康检查…", flush=True)
            time.sleep(5)
    check = subprocess.run(
        [sys.executable, "scripts/verify_production.py"], cwd=ROOT, check=False
    )
    if check.returncode:
        raise RuntimeError("原HTTPS/认证入口检查失败，拒绝开放公网。")
    print(
        "本地生产演练环境已就绪：https://localhost:18443（保留邀请认证）。", flush=True
    )


def install():
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    if BINARY.exists() and hashlib.sha256(BINARY.read_bytes()).hexdigest() == DIGEST:
        return
    # Reuse only a digest-verified official binary; /tmp may have been cleared.
    temporary_binary = Path("/tmp/stockinsight-quick-tunnel-1qisi_g3/cloudflared")
    if (
        temporary_binary.exists()
        and hashlib.sha256(temporary_binary.read_bytes()).hexdigest() == DIGEST
    ):
        shutil.copyfile(temporary_binary, BINARY)
    else:
        if os.uname().machine != "x86_64":
            raise RuntimeError(
                "此固定版本工具适用于Linux x86_64，请另行准备官方对应架构工具。"
            )
        url = "https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-linux-amd64"
        partial = BINARY.with_suffix(".partial")
        try:
            for attempt in range(3):
                try:
                    with (
                        urllib.request.urlopen(url, timeout=30) as source,
                        partial.open("wb") as target,
                    ):
                        shutil.copyfileobj(source, target)
                    break
                except OSError:
                    if attempt == 2:
                        raise RuntimeError(
                            "官方工具下载失败，保留TLS校验；请检查出站网络。"
                        ) from None
            if hashlib.sha256(partial.read_bytes()).hexdigest() != DIGEST:
                raise RuntimeError("官方工具校验失败，拒绝执行。")
            partial.replace(BINARY)
        finally:
            partial.unlink(missing_ok=True)
    BINARY.chmod(0o700)
    print(
        "官方cloudflared已校验，保存在Git忽略的data/tools；未安装系统软件。", flush=True
    )


def public(seconds, local_only=False):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "public.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "已有公网窗口运行；先执行 ./stockinsight.sh public-stop。"
            ) from None
        start()
        install()
        proxy = inspect(f"{PROJECT}-proxy-1")
        if "stockinsight-m6_ingress" not in proxy["NetworkSettings"]["Networks"]:
            raise RuntimeError("现有私网拓扑与本机脚本不符，拒绝修改。")
        output = (
            ROOT
            / "data/acceptance"
            / ("public-" + time.strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:8])
        )
        # The tunnel creates this directory; never overwrite old evidence.

        owner_token = uuid4().hex
        name = "stockinsight-public-preview-" + owner_token[:8]
        runtime_config = RUNTIME / ("proxy-" + owner_token)
        runtime_config.mkdir(mode=0o755)
        runtime_config.chmod(0o755)
        shutil.copyfile(
            ROOT / "deploy/Caddyfile.public-preview", runtime_config / "Caddyfile"
        )
        (runtime_config / "Caddyfile").chmod(0o444)
        (RUNTIME / "public.json").write_text(
            json.dumps(
                {
                    "output": str(output),
                    "container": name,
                    "owner_token": owner_token,
                    "config_directory": str(runtime_config),
                }
            )
        )
        owned = None
        child = None
        try:
            owned = docker(
                "run",
                "-d",
                "--name",
                name,
                "--label",
                "stockinsight.temporary-public=true",
                "--label",
                "stockinsight.public-owner=" + owner_token,
                "--network",
                "stockinsight-m6_ingress",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=32m",
                "--tmpfs",
                "/data:rw,nosuid,size=32m",
                "--tmpfs",
                "/config:rw,noexec,nosuid,size=8m",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "NET_BIND_SERVICE",
                "--security-opt",
                "no-new-privileges:true",
                "--memory",
                "256m",
                "--cpus",
                "0.5",
                "--log-opt",
                "max-size=5m",
                "--log-opt",
                "max-file=2",
                "-p",
                "127.0.0.1:18843:443",
                "--mount",
                f"type=bind,src={runtime_config},dst=/etc/caddy,readonly",
                proxy["Image"],
                quiet=True,
            ).strip()
            ca = RUNTIME / "public-ca.crt"
            ca.unlink(missing_ok=True)
            for _ in range(30):
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        owned,
                        "cat",
                        "/data/caddy/pki/authorities/local/root.crt",
                    ],
                    capture_output=True,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.startswith(
                    b"-----BEGIN CERTIFICATE-----"
                ):
                    ca.write_bytes(result.stdout)
                    ca.chmod(0o600)
                    break
                if not inspect(owned)["State"]["Running"]:
                    raise RuntimeError("独立匿名代理启动失败，原服务保持不变。")
                time.sleep(1)
            else:
                raise RuntimeError("独立代理CA尚未就绪，拒绝开放。")
            print(
                (
                    "正在验证本地匿名入口，不建立公网连接。"
                    if local_only
                    else f"正在验证匿名只读公网入口，窗口 {seconds} 秒；请保留此终端。"
                ),
                flush=True,
            )
            command = [
                sys.executable,
                "deploy/acceptance/business_tunnel.py",
                "--anonymous",
                "--binary",
                str(BINARY),
                "--output",
                str(output),
                "--duration",
                str(seconds),
            ]
            if local_only:
                command.append("--local-only")
            child = subprocess.Popen(command, cwd=ROOT)
            if child.wait():
                raise RuntimeError(
                    f"公网验证失败或窗口被中断，已关闭本轮入口。脱敏证据：{output}"
                )
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            # docker run can create a stopped container even when start fails.
            # Inspect only this unique name and require the exact ownership label.
            cleanup = subprocess.run(
                ["docker", "inspect", name], capture_output=True, text=True, check=False
            )
            if cleanup.returncode == 0:
                item = json.loads(cleanup.stdout)[0]
                if (
                    item["Config"].get("Labels", {}).get("stockinsight.public-owner")
                    != owner_token
                ):
                    raise RuntimeError("清理时所有权不符，拒绝删除容器。")
                if child is None or child.returncode:
                    logs = subprocess.run(
                        ["docker", "logs", "--tail", "30", item["Id"]],
                        capture_output=True,
                        check=False,
                    )
                    (
                        RUNTIME / ("public-start-failure-" + owner_token + ".log")
                    ).write_bytes(logs.stdout + logs.stderr)
                docker("rm", "-f", item["Id"], quiet=True)
                print("本轮匿名代理已清理，原服务继续运行。", flush=True)
            shutil.rmtree(runtime_config)


def reload_public():
    metadata = json.loads((RUNTIME / "public.json").read_text())
    item = inspect(metadata["container"])
    if (
        not item["State"]["Running"]
        or item["Config"].get("Labels", {}).get("stockinsight.public-owner")
        != metadata["owner_token"]
    ):
        raise RuntimeError("没有当前脚本所有的运行中匿名代理，拒绝reload。")
    directory = Path(metadata["config_directory"])
    if directory != RUNTIME / ("proxy-" + metadata["owner_token"]):
        raise RuntimeError("配置目录异常，拒绝reload。")
    temporary = directory / "Caddyfile.new"
    shutil.copyfile(ROOT / "deploy/Caddyfile.public-preview", temporary)
    temporary.chmod(0o444)
    try:
        docker(
            "exec",
            item["Id"],
            "caddy",
            "adapt",
            "--config",
            "/etc/caddy/Caddyfile.new",
            "--adapter",
            "caddyfile",
            "--validate",
            quiet=True,
        )
    except RuntimeError:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "新匿名代理配置校验失败，保留运行配置，不执行reload。"
        ) from None
    temporary.replace(directory / "Caddyfile")
    # USR1 reloads the startup file without enabling an HTTP admin endpoint.
    docker("kill", "--signal", "USR1", item["Id"], quiet=True)
    print("已请求本轮匿名代理热加载；不重建容器，原认证入口和数据库不变。")


def status():
    docker(
        "ps",
        "--filter",
        "name=stockinsight-",
        "--format",
        "table {{.Names}}\t{{.Status}}\t{{.Ports}}",
    )
    path = RUNTIME / "public.json"
    if path.exists():
        state_file = Path(json.loads(path.read_text())["output"]) / "state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            print(
                json.dumps(
                    {
                        key: state.get(key)
                        for key in (
                            "url",
                            "expires_at",
                            "gates_passed",
                            "process_stopped",
                        )
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )


def stop():
    path = RUNTIME / "public.json"
    if not path.exists():
        print("没有由根目录脚本开启的公网窗口。")
        return
    output = Path(json.loads(path.read_text())["output"])
    if output.parent != ROOT / "data/acceptance":
        raise RuntimeError("运行记录路径异常，拒绝操作。")
    if not output.is_dir():
        raise RuntimeError("窗口正在准备；请在原启动终端按Ctrl+C取消。")
    (output / "STOP").touch()
    print("已请求停止本轮Tunnel及独立匿名代理；原业务容器不会停止。")


def main():
    os.chdir(ROOT)
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "start",
            "public",
            "public-stop",
            "public-reload",
            "status",
            "install-tunnel",
        ),
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=28800,
        help="Public window duration, default 8 hours; 60..86400",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only validate the isolated local public proxy, without a tunnel",
    )
    args = parser.parse_args()
    if not 60 <= args.seconds <= 86400:
        parser.error("时间必须为60..86400秒")
    if args.command == "start":
        start()
    elif args.command == "public":
        public(args.seconds, args.local_only)
    elif args.command == "public-stop":
        stop()
    elif args.command == "public-reload":
        reload_public()
    elif args.command == "status":
        status()
    else:
        install()


if __name__ == "__main__":

    def interrupt(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as error:
        print(
            str(error)
            if isinstance(error, RuntimeError)
            else "操作中断或环境不可用；不输出敏感错误详情。",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
