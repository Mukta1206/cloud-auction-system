import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "change_this_to_long_random_key_12345"

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "auction.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    PERMANENT_SESSION_LIFETIME = 300
    SESSION_REFRESH_EACH_REQUEST = True