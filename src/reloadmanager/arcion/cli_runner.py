import subprocess

from reloadmanager.mixins.logging_mixin import LoggingMixin


class CliRunner(LoggingMixin):
    def __init__(self, file_writer=None, process_runner=None):
        self.file_writer = file_writer if file_writer else self._default_file_writer
        self.process_runner = process_runner if process_runner else self._default_process_runner

    def run(self, command, log_file):
        try:
            result = self.process_runner(command)
            self.file_writer(log_file, result.stdout)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Command: '{' '.join(command)}' failed with exit code {e.returncode}")
            output = e.output.strip() if e.output else 'No output captured'
            indented_output = "\n\t\t" + output.replace('\n', '\n\t\t')
            print(f"\tCaptured output: {indented_output}")
            self.file_writer(log_file, e.output if e.output else '')
            raise
        except Exception as e:
            print(f"Command: '{' '.join(command)}' failed")
            raise e

    @staticmethod
    def _default_file_writer(log_file, content):
        with open(log_file, 'w') as f:
            f.write(content)

    @staticmethod
    def _default_process_runner(command):
        return subprocess.run(
            command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
