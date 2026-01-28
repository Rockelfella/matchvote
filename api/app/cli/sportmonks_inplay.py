from __future__ import annotations

from app.core.sportmonks.service import poll_inplay_and_persist


def main() -> None:
    result = poll_inplay_and_persist()
    print(result)


if __name__ == "__main__":
    main()
