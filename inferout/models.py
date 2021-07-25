import json
import copy
import logging
import re
from .cluster import Cluster
from inferout import cluster, exceptions, utils

NAMESPACE_REGEX = re.compile("^[a-z][a-z0-9\-_]{2,9}$") #min len 3, max len 10
NAMESPACE_KEY = "{{@namespace-{}}}"
NAMESPACE_KEY_REGEX = re.compile('{@namespace-(.*)}$')

MODEL_REGEX = re.compile("^[a-z][a-z0-9\-_]{0,19}$") #min len 1, max len 20
MODEL_KEY = "{{@model-{}}}"
MODEL_KEY_REGEX = re.compile('{@model-(.*)}$')

MODEL_VERSION_KEY = "@model_version-{}"
MODEL_VERSION_KEY_REGEX = re.compile('@model_version-(.*)$')

MODEL_INSTANCE_KEY = "@model_instance-{}"
MODEL_INSTANCE_KEY_REGEX = re.compile('@model_instance-(.*)$')

MODEL_INSTANCE_TERMINATING_DURATION = 60

NAMESPACE_DEFAULT_SETTINGS = {
    "storage_engine": "inferout.storage_engines.local_files",
    "serving_engine": "inferout.serving_engines.echo",
    "instances_per_model": {
        "min": 1,
        "max": 4,
        "target": 2
    },
    "max_version_history": 10
}

class ModelNamespace(object):
    def __init__(self, cluster: Cluster, id:str) -> None:
        if NAMESPACE_REGEX.match(id) is None:
            raise ValueError("invalid Namespace name %s", id)
        self.cluster = cluster
        self.id = id
        self.settings = None

        self.redis_key = self.cluster.get_redis_key(NAMESPACE_KEY.format(self.id))

    async def read_from_redis(self):
        data = await self.cluster.redis.hgetall(
            self.redis_key
        )
        if not data:
            raise exceptions.NotFoundException()

        self.settings = json.loads(data["settings"])
    
    async def read(self):
        await self.read_from_redis()

    async def save_to_redis(self):
        data = {"settings": json.dumps(self.settings)}
        await self.cluster.redis.hset(
            self.redis_key,
            mapping=data
        )
    
    async def save(self):
        settings = copy.deepcopy(NAMESPACE_DEFAULT_SETTINGS)
        self.settings = utils.deep_update(settings, self.settings or {})

        await self.save_to_redis()
    
    @classmethod
    async def get_all_as_list(cls, cluster):
        data = []
        async for each in cluster.redis.scan_iter(
            cluster.get_redis_key(NAMESPACE_KEY.format('*'))
            ):
            each_data = await cluster.redis.hgetall(each)
            each_data["id"] = NAMESPACE_KEY_REGEX.search(each).group(1)
            each_data["settings"] = json.loads(each_data["settings"])
            data.append(each_data)
        return data

class Model(object):
    def __init__(self, namespace: ModelNamespace, id: str) -> None:
        if MODEL_REGEX.match(id) is None:
            raise ValueError("invalid Model name %s", id)
        self.id = id
        self.namespace = namespace
        self.cluster = namespace.cluster
        
        self.latest_version = None
        self.latest_version_id = None

        self.parameters = None

        self.redis_key = self.cluster.get_redis_key(
            self.namespace.id,
            MODEL_KEY.format(self.id))
    
    @classmethod
    async def get_all_as_list(cls, cluster:Cluster, namespace:ModelNamespace):
        data = []
        async for each in cluster.redis.scan_iter(
            cluster.get_redis_key(namespace.id, MODEL_KEY.format('*'))
            ):
            each_data = await cluster.redis.hgetall(each)
            each_data["id"] = MODEL_KEY_REGEX.search(each).group(1)
            each_data["parameters"] = json.loads(each_data["parameters"])
            each_data["latest_version_id"] = int(each_data["latest_version_id"])
            data.append(each_data)
        return data

    async def read_from_redis(self):
        data = await self.cluster.redis.hgetall(
            self.redis_key
        )
        if not data:
            raise exceptions.NotFoundException()

        self.latest_version_id = int(data["latest_version_id"])
        self.parameters = json.loads(data["parameters"])

    async def read(self):
        await self.read_from_redis()
        self.latest_version = ModelVersion(model=self, id=self.latest_version_id)
        await self.latest_version.read()

    async def save_to_redis(self):
        data = {
            "latest_version_id": self.latest_version_id,
            "parameters": json.dumps(self.parameters)
        }
        await self.cluster.redis.hset(
            self.redis_key,
            mapping=data
        )

    async def save(self):
        self.parameters = self.parameters or {}
        if self.latest_version_id is None:
            self.latest_version_id = 1
        else:
            self.latest_version_id += 1
        latest_version = ModelVersion(model=self, id=self.latest_version_id)
        latest_version.parameters = self.parameters
        await latest_version.save()
        self.latest_version = self.parameters
        await self.save_to_redis()

class ModelVersion(object):
    def __init__(self, model:Model, id:str) -> None:
        self.model = model
        self.cluster = model.cluster
        self.id = id
        self.parameters = None

        self.redis_key = self.cluster.get_redis_key(
            self.model.namespace.id,
            utils.covert_to_redis_slot(self.model.id),
            MODEL_VERSION_KEY.format(self.id))
        
    @classmethod
    async def get_all_as_list(cls, cluster:Cluster, model: Model):
        data = []
        async for each in cluster.redis.scan_iter(
            cluster.get_redis_key(
                model.namespace.id,
                utils.covert_to_redis_slot(model.id),
                MODEL_VERSION_KEY.format("*")
                )
            ):
            each_data = await cluster.redis.hgetall(each)
            each_data["id"] = int(MODEL_VERSION_KEY_REGEX.search(each).group(1))
            each_data["parameters"] = json.loads(each_data["parameters"])
            data.append(each_data)
        return sorted(data, key=lambda x: x["id"], reverse=True)

    async def read_from_redis(self):
        data = await self.cluster.redis.hgetall(
            self.redis_key
        )
        if not data:
            raise exceptions.NotFoundException()

        self.parameters = json.loads(data["parameters"])

    async def read(self):
        await self.read_from_redis()

    async def save_to_redis(self):
        data = {
            "parameters": json.dumps(self.parameters)
        }
        await self.cluster.redis.hset(
            self.redis_key,
            mapping=data
        )

    async def save(self):
        self.parameters = self.parameters or {}
        await self.save_to_redis()

class ModelInstance(object):
    def __init__(self, model_version:ModelVersion, id) -> None:
        self.id = id
        self.model_version = model_version
        self.storage_context = None
        self.serving_context = None # avaiable in redis
        self.worker_serving_context = None #only avaiable in assigned worker
        self.worker_id = None
        self.state = None
        self.error_messages = None

        self.model = model_version.model

        self.model_version_id = model_version.id

        self.cluster = model_version.cluster
    
        self.redis_key = self.cluster.get_redis_key(
            self.model.namespace.id,
            utils.covert_to_redis_slot(self.model.id),
            str(self.model_version.id),
            MODEL_INSTANCE_KEY.format(self.id))

    async def read_from_redis(self):
        data = await self.cluster.redis.hgetall(
            self.redis_key
        )
        if not data:
            raise exceptions.NotFoundException()
        self.worker_id = data["worker_id"]
        self.state = data["state"]
        self.storage_context = json.loads(data["storage_context"])
        self.serving_context = json.loads(data["serving_context"])
        self.error_messages = json.loads(data["error_messages"])

    async def read(self):
        await self.read_from_redis()


    async def save_to_redis(self):
        data = {
            "worker_id": self.worker_id,
            "state": self.state,
            "storage_context": json.dumps(self.storage_context),
            "serving_context": json.dumps(self.serving_context),
            "error_messages": json.dumps(self.error_messages)
        }
        await self.cluster.redis.hset(
            self.redis_key,
            mapping=data
        )
        if self.state == "terminating":
            ttl = await self.cluster.redis.ttl(self.redis_key)
            if ttl == -1:
                await self.cluster.redis.expire(
                    self.redis_key,
                    MODEL_INSTANCE_TERMINATING_DURATION
                )

    async def save(self):
        self.storage_context = self.storage_context or {}
        self.serving_context = self.serving_context or {}
        await self.save_to_redis()
    
    @classmethod
    async def get_all_as_list(cls, cluster:Cluster, model: Model, version:ModelVersion=None):
        data = []
        if version is None:
            version_id_key = "*" #any version
        else:
            version_id_key = version.id
        async for each in cluster.redis.scan_iter(
            cluster.get_redis_key(
                model.namespace.id,
                utils.covert_to_redis_slot(model.id),
                version_id_key,
                MODEL_INSTANCE_KEY.format("*")
                )
            ):
            each_data = await cluster.redis.hgetall(each)
            each_data["id"] = MODEL_INSTANCE_KEY_REGEX.search(each).group(1)
            each_data["model_version_id"] = utils.split_redis_key(each)[-2]
            each_data["worker_id"] = each_data["worker_id"]
            each_data["state"] = each_data["state"]
            each_data["storage_context"] = json.loads(each_data["storage_context"])
            each_data["serving_context"] = json.loads(each_data["serving_context"])
            each_data["error_messages"] = json.loads(each_data["error_messages"])
            data.append(each_data)
        return sorted(data, key=lambda x: x["model_version_id"], reverse=True)
    