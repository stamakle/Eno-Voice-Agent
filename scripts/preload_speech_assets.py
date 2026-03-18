from english_tech.speech import speech_service


def main() -> None:
    speech_service._ensure_piper_assets()  # noqa: SLF001 - intentional preload helper
    print('speech assets ready')


if __name__ == '__main__':
    main()
