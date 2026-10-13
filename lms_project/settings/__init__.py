import os


if os.environ.get("DJANGO_ENV", "development").lower() == "production":
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
