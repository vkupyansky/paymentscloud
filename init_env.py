"""Создание локальной конфигурации без перезаписи существующего файла."""

import os
import secrets
import tempfile
from pathlib import Path


def main() -> None:
    target = Path(".env")
    if target.exists():
        print(".env уже существует и сохранён")
        return
    content = (
        Path(".env.example")
        .read_text()
        .replace("WEBHOOK_SECRET=\n", f"WEBHOOK_SECRET={secrets.token_urlsafe(32)}\n")
    )
    with tempfile.NamedTemporaryFile(mode="w", dir=".", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, target)
        finally:
            temporary.unlink()
    print("Создан .env с правами 0600. Заполните внешние настройки в редакторе")


if __name__ == "__main__":
    main()
