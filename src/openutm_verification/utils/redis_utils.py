"""
Redis utilities for caching and data storage.
"""

import logging
from os import environ as env

import redis
from dotenv import find_dotenv, load_dotenv
from walrus import Database

# Load .env file if it exists
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)

logger = logging.getLogger("django")


def get_redis():
    """Get Redis client instance."""
    redis_host = env.get("REDIS_HOST", "redis")
    redis_port = int(env.get("REDIS_PORT", 6379))
    redis_password = env.get("REDIS_PASSWORD", None)

    if redis_password:
        r = redis.Redis(host=redis_host, port=redis_port, password=redis_password, decode_responses=True, encoding="utf-8")
    else:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, encoding="utf-8")

    return r


def get_walrus_database():
    """Get Walrus database instance."""
    redis_host = env.get("REDIS_HOST", "redis")
    redis_port = int(env.get("REDIS_PORT", 6379))
    redis_password = env.get("REDIS_PASSWORD", None)

    if redis_password:
        db = Database(host=redis_host, port=redis_port, password=redis_password)
    else:
        db = Database(host=redis_host, port=redis_port)
    return db
