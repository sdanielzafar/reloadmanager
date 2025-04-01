import subprocess


def run_cli_cmd(command: list[str], log_file: str) -> str:
    try:
        result = subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with open(log_file, 'w') as f:
            f.write(result.stdout)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command: '{' '.join(command)}' failed with exit code {e.returncode}")
        output = e.output.strip() if e.output else 'No output captured'
        indented_output = "\n\t\t" + output.replace('\n', '\n\t\t')
        print(f"\tCaptured output: {indented_output}")
        with open(log_file, 'w') as f:
            f.write(e.output if e.output else '')
        raise
    except Exception as e:
        print(f"Command: '{' '.join(command)}' failed")
        raise e
