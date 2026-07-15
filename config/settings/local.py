from .base import *
from decouple import config

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS += [
    "django.contrib.admindocs",  # optional, handy locally
]
