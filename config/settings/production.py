from .base import *
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured


DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

if PAYMENT_GATEWAY == "fake":
    raise ImproperlyConfigured("The fake payment gateway must never run in production.")
