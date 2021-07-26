import asyncio
from asyncio.tasks import sleep
from copy import deepcopy
import json
import time

import aioredis
import async_timeout
from . import exceptions

from configargparse import Namespace
from inferout.management_api import workers
import logging

from .cluster import Cluster
from . import utils
from .storage_engines.base import StorageEngine
from .serving_engines.base import ServingEngine
from .worker import (Worker, WORKER_KEY)
from .models import (
    MODEL_INSTANCE_KEY,
    ModelNamespace,
    Model,
    ModelVersion,
    ModelInstance,
    MODEL_KEY,
    MODEL_KEY_REGEX,
    MODEL_INSTANCE_KEY_REGEX)
from . import utils

SCHEDULER_INTERVAL = 5
SCHEDULER_SLEEP_WARNNING_DURATION = 3
SCHEDULER_LOCK_ERROR_SLEEP_DURATION = 0.5
SCHEDULER_KEY = "@scheduler"
MODEL_INSTANCE_SCHEDULED_SLEEP_DURATION = 0.1

class Scheduler(object):
    def __init__(self, cluster: Cluster, worker: Worker) -> None:
        self.cluster = cluster
        self.worker = worker
        self.shutdown_requested = False

        self.active_workers_map = {}

    async def select_worker(self, model_version: ModelVersion):
        storage_engine = model_version.model.namespace.settings.get("storage_engine")
        serving_engine = model_version.model.namespace.settings.get("serving_engine")
        workers = self.active_workers_map.values()
        if storage_engine:
            workers = filter(lambda x: storage_engine in x["available_storage_engines"], workers)
        if serving_engine:
            workers = filter(lambda x: serving_engine in x["available_serving_engines"], workers)
        
        if not workers:
            return None
        workers = sorted(workers, key=lambda x: int(x["model_instances_count"]))
        return workers[0]["id"]
    
    async def refresh_active_workers_data(self):
        active_workers_map = {}
        for each_worker in await self.worker.get_all_workers_data():
            if each_worker["state"]=="serving":
                active_workers_map[each_worker["id"]] = each_worker
        self.active_workers_map = active_workers_map

    async def schedule_once(self):
        cluster = self.cluster
        async for each in cluster.redis.scan_iter(
            cluster.get_redis_key(
                "*",#any namespace
                MODEL_KEY.format("*"),#any model
                )
            ):

            ns_id, model_key = utils.split_redis_key(each)[1:]
            model_id = MODEL_KEY_REGEX.search(model_key).group(1)
            ns = ModelNamespace(cluster=cluster, id=ns_id)
            try:
                await ns.read()
            except exceptions.NotFoundException:
                continue
            model = Model(namespace=ns,id=model_id)
            try:
                await model.read()
            except exceptions.NotFoundException:
                continue
            logging.debug("looking for pending model instances of namespace=%s model=%s version=%s", ns.id, model.id, model.latest_version_id)
            latest_model_instances = []
            outdated_model_instances = []
            async for each_instance_key in cluster.redis.scan_iter(
                cluster.get_redis_key(
                    ns.id,
                    utils.covert_to_redis_slot(model.id),
                    "*", #any version
                    MODEL_INSTANCE_KEY.format("*") #any instance
                    )
                ):
                logging.debug("each_instance_key %s", each_instance_key)
                version_id, instance_key = utils.split_redis_key(each_instance_key)[-2:]
                version_id = int(version_id)
                instance_id = MODEL_INSTANCE_KEY_REGEX.search(instance_key).group(1)

                model_version = ModelVersion(model=model, id=version_id)
                try:
                    await model_version.read()
                except exceptions.NotFoundException:
                    continue

                model_instance = ModelInstance(model_version=model_version,id=instance_id)
                try:
                    await model_instance.read()
                except exceptions.NotFoundException:
                    continue
                if model_instance.state != "terminating" and (model_instance.worker_id not in self.active_workers_map):
                    model_instance.state = "terminating"
                    await model_instance.save()
                    continue
                if model.latest_version_id == model_instance.model_version_id:
                    latest_model_instances.append(model_instance)
                else:
                    outdated_model_instances.append(model_instance)
            logging.debug("outdated_model_instances: %s", ",".join([x.id for x in outdated_model_instances]))
            logging.debug("latest_model_instances: %s", ",".join([x.id for x in latest_model_instances]))
            
            latest_serving_model_instances = list(filter(lambda x: x.state=="serving",latest_model_instances))
            if len(latest_serving_model_instances) >= int(ns.settings["instances_per_model"]["target"]):
                for outdated_model_instance in outdated_model_instances:
                    if outdated_model_instance.state == "terminating":
                        continue
                    event_data = {
                        "namespace_id": ns.id,
                        "model_id": outdated_model_instance.model.id,
                        "model_version_id": outdated_model_instance.model_version.id,
                        "model_instance_id": outdated_model_instance.id,
                        "worker_id": outdated_model_instance.worker_id
                        }
                    await self.cluster.redis.publish(
                        self.cluster.get_redis_channel_key(
                            WORKER_KEY.format(outdated_model_instance.worker_id)
                        ),
                        message=json.dumps({
                                "event_type": "TERMINATE_MODEL_INSTANCE",
                                "event_data": event_data
                            })
                    )
                    logging.info("terminating model instance %s", event_data)

            no_new_instances_required = int(ns.settings["instances_per_model"]["target"]) - len(latest_model_instances)
            logging.debug("New model instances required: %d.", no_new_instances_required)

            for i in range(no_new_instances_required):
                new_model_instance = ModelInstance(
                    model_version=model.latest_version,
                    id=utils.get_uuid_as_string())
                new_model_instance.worker_id = await self.select_worker(
                    model_version=model.latest_version)
                if new_model_instance.worker_id is None:
                    logging.error("No sutable workers available for namespace=%s model=%s version=%s",ns.id,model.id, model.latest_version_id)
                    break
                new_model_instance.state = "scheduled"
                await new_model_instance.save()
                event_data = {
                    "namespace_id": ns.id,
                    "model_id": new_model_instance.model.id,
                    "model_version_id": new_model_instance.model_version.id,
                    "model_instance_id": new_model_instance.id,
                    "worker_id": new_model_instance.worker_id
                    }
                await self.cluster.redis.publish(
                    self.cluster.get_redis_channel_key(
                        WORKER_KEY.format(new_model_instance.worker_id)
                    ),
                    message=json.dumps({
                            "event_type": "MODEL_INSTANCE_SCHEDULED",
                            "event_data": event_data
                        })
                )
                await asyncio.sleep(MODEL_INSTANCE_SCHEDULED_SLEEP_DURATION)
                logging.info("scheduled model instance %s", event_data)

    async def handle_worker_update(self, event_data):
        logging.debug("handle_worker_update %s", event_data)
        worker_id = event_data["worker_id"]
        worker_data = await self.worker.get_remote_worker_data(worker_id=worker_id)
        if worker_data["state"] == "serving":
            self.active_workers_map[worker_id] = worker_data
        else:
            if worker_id in self.active_workers_map:
                del self.active_workers_map[worker_id]

    async def channel_reader(self):
        while not self.shutdown_requested:
            message = None
            try:
                async with async_timeout.timeout(1):
                    message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                    await asyncio.sleep(0.01)
            except asyncio.TimeoutError:
                pass
            if message is not None:
                logging.debug(f"(Scheduler Reader) Message Received: {message}")
                data = json.loads(message["data"])
                if data["event_type"] == "WORKER_UPDATE":
                    await self.handle_worker_update(data["event_data"])
                else:
                    logging.info("Unknown event type %s, skipping", data["event_type"])
    
    async def setup_pubsub(self):
        self.pubsub = self.cluster.redis.pubsub()
        await self.pubsub.subscribe(
            self.cluster.get_redis_channel_key(SCHEDULER_KEY)
            )
        return self.channel_reader()

    async def schedule_forever(self):
        while not self.shutdown_requested:
            try:
                async with self.cluster.get_async_lock(SCHEDULER_KEY):
                    start_time = time.time()
                    await self.refresh_active_workers_data()
                    await self.schedule_once()
                    end_time = time.time()
                    time_to_sleep = SCHEDULER_INTERVAL - (end_time - start_time)
                    if time_to_sleep <= 0:
                        raise Exception("scheduler taking unexpectedly longer")
                    if time_to_sleep <= SCHEDULER_SLEEP_WARNNING_DURATION:
                        logging.warning("scheduler taking longer, took %f, sleeping for %f",(end_time - start_time), time_to_sleep)
                    logging.debug("sleeping for %f",time_to_sleep)
                    await asyncio.sleep(time_to_sleep)
            except aioredis.exceptions.LockError:
                logging.debug("Unable to acquire lock for scheduler")
                await asyncio.sleep(SCHEDULER_LOCK_ERROR_SLEEP_DURATION)