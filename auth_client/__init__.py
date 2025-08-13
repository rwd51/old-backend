from django.conf import settings
from .client import *
# rafi
# api_client = PriyoClient('4f155557-f86b-46b3-9c6c-5d757b554dbb')
# robin
# api_client = PriyoClient('fce7f94c-44d0-454e-905b-f0bb8b6b17d5')
# live
# api_client = PriyoClient('948ebab7-cf27-434c-a5c4-82c19c599a3a')
api_client = PriyoClient(settings.AUTH_API_KEY)