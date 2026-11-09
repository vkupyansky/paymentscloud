import subprocess
import sys


def main() -> None:
    for command in (
        ["ruff", "format", "--check", "."],
        ["ruff", "check", "."],
        [sys.executable, "-m", "pytest", "-W", "error"],
    ):
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
