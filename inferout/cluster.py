import aioredis
from . import utils
from .exceptions import InvalidClusterError
import logging

CLUSTER_BOOTSTRAP_VERSION = "0.0"

REDIS_LOCK_TIMEOUT = 10
REDIS_LOCK_BLOCKING_TIMEOUT = 0

CLUSTER_INFO_KEY = '@cluster_info'


class Cluster(object):
    def __init__(self, redis: aioredis.client.Redis, redis_key_prefix: str, name: str) -> None:
        self.redis = redis
        self.redis_key_prefix = redis_key_prefix
        self.name = name
        self.version = None
    
    def get_async_lock(self, *args):
        return self.redis.lock(
            name=utils.get_redis_key(self.redis_key_prefix, 'lock', *args),
            timeout=REDIS_LOCK_TIMEOUT,
            blocking_timeout=REDIS_LOCK_BLOCKING_TIMEOUT,
            thread_local=False)
    
    def get_redis_key(self, *args):
        return utils.get_redis_key(self.redis_key_prefix, *args)
    
    def get_redis_channel_key(self, *args):
        return utils.get_redis_key(self.redis_key_prefix, 'channel', *args)
    
    async def sync(self):
        cluster_info = await self.redis.hgetall(self.get_redis_key(CLUSTER_INFO_KEY))
        if not cluster_info:
            raise InvalidClusterError("Does Not exist.")
        if cluster_info['name'] != self.name:
            raise InvalidClusterError("Name mismatch")
        self.version = cluster_info['version']


    async def bootstrap(self):
        async with self.get_async_lock(CLUSTER_INFO_KEY):
            existing_cluster_info = await self.redis.hgetall(self.get_redis_key(CLUSTER_INFO_KEY))
            if(existing_cluster_info):
                logging.error("Existing cluster found")
                logging.info("Cluster Info: %s", existing_cluster_info)
            else:
                cluster_info = {
                    "name": self.name,
                    "version": CLUSTER_BOOTSTRAP_VERSION
                    }
                await self.redis.hset(self.get_redis_key(CLUSTER_INFO_KEY),
                mapping=cluster_info)
                logging.info("Bootstrapping Cluster: %s", cluster_info)