import os

from config import settings


def inject_captcha_extension(browser_context) -> None:
    extension_path = settings.NOPECHA_EXTENSION_PATH
    if not os.path.exists(extension_path):
        return
    try:
        browser_context.add_init_script(path=extension_path)
    except Exception:
        pass
