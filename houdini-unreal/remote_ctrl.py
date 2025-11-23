import time
from pathlib import Path

# remote_execution is unreal plugin. need install it. google it.
from remote_execution import RemoteExecution
import json
import constants, importlib
importlib.reload(constants)

remote_exec = RemoteExecution()

def run_and_send_arguments(args: list) -> None:
    """Unrealに信号を送信。Python実行

    Args:
        args ( list ) : Unrealに送信する引数リスト。出力パスとFBXの名前

    Return:
        Unrealに引数を渡しつつPythonを実行する : None
    """

    remote_exec.start()
    time.sleep(1)

    if remote_exec.remote_nodes:
        remote_exec.open_command_connection(remote_exec.remote_nodes[0])
        remote_exec.run_command(f"main.py {args}")

        print("done")
    remote_exec.stop()