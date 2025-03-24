import subprocess


def run_cli_cmd(command: list[str]) -> str:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command: '{' '.join(command)}' failed with exit code {e.returncode}")
        stderr: str = "\n\t\t" + e.stderr.strip().replace('\n', '\n\t\t')
        stdout: str = "\n\t\t" + e.stdout.strip().replace('\n', '\n\t\t')
        print(f"\tThe command's stderr: {stderr if e.stderr else 'No stderr available'}")
        print(f"\tThe command's stdout: {stdout if e.stdout else 'No stdout available'}")
        raise e
    except Exception as e:
        print(f"Command: '{' '.join(command)}' failed")
        raise e
