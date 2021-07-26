import asyncio
from copy import deepcopy
import json
from os import name

from inferout.models import (
    Model,
    ModelInstance,
    ModelNamespace,
    ModelVersion)
import async_timeout
import logging
from functools import partial

from .cluster import Cluster
from . import utils
import signal
from . import management_api
from . import serving_api
from aiohttp import web
import re
from .storage_engines.base import StorageEngine
from .serving_engines.base import ServingEngine
from . import exceptions
from . import worker_annotators

import os
import sys
sys.path.append(os.getcwd())

WORKER_ANNOTATORS = [worker_annotators.serving_endpoint_from_options]

WORKER_KEY = '{{@worker-{}}}'
WORKER_KEY_REGEX = re.compile('{@worker-(.*)}$')
WORKER_REPORT_SLEEP_DURATION = 5
WORKER_REPORT_EXPIRE_MULTIPLIER = 2
WORKER_REPORT_EXPIRE_ADDITION = 10

class Worker(object):
    def __init__(self, cluster: Cluster, options) -> None:
        self.cluster = cluster
        self.options = options
        self.id = utils.get_uuid_as_string()
        self.worker_key = WORKER_KEY.format(self.id)
        self.state = None
        self.shutdown_requested = False
        self.storage_engines = {}
        self.serving_engines = {}

        self.serving_endpoint = None

        self.local_model_instances = {}
    
    async def report_forever(self):
        while True:
            await self.report_once()
            if self.shutdown_requested:
                break
            await asyncio.sleep(WORKER_REPORT_SLEEP_DURATION)

    async def report_once(self, send_events=False):
            from .scheduler import SCHEDULER_KEY
            logging.debug("Reporting %s", self.worker_key)
            data = {
                "state": self.state,
                "serving_endpoint": self.serving_endpoint,
                "available_storage_engines": json.dumps(list(self.storage_engines.keys())),
                "available_serving_engines": json.dumps(list(self.serving_engines.keys())),
                "model_instances_count": len(self.local_model_instances)
                }
            logging.debug("Reporting %s %s", self.worker_key, data)
            
            redis_key = self.cluster.get_redis_key(self.worker_key)
            async with self.cluster.redis.pipeline(transaction=True) as pipe:
                pipe.hset(
                    redis_key,
                    mapping=data
                    )
                pipe.expire(redis_key,
                WORKER_REPORT_SLEEP_DURATION*WORKER_REPORT_EXPIRE_MULTIPLIER
                )
                await pipe.execute()
            if send_events:
                event_data = {
                    "worker_id": self.id,
                    "state": self.state,
                    "model_instances_count": len(self.local_model_instances)
                    }
                await self.cluster.redis.publish(
                    self.cluster.get_redis_channel_key(
                        SCHEDULER_KEY
                    ),
                    message=json.dumps({
                            "event_type": "WORKER_UPDATE",
                            "event_data": event_data
                        })
                )
    
    async def get_worker_data_from_redis(self, redis_key):
        worker_data = await self.cluster.redis.hgetall(redis_key)
        worker_data["id"] = WORKER_KEY_REGEX.search(redis_key).group(1)
        worker_data["available_storage_engines"] = json.loads(worker_data["available_storage_engines"])
        worker_data["available_serving_engines"] = json.loads(worker_data["available_serving_engines"])
        worker_data["model_instances_count"] = int(worker_data["model_instances_count"])
        return worker_data

    async def get_all_workers_data(self):
        data = []
        async for each in self.cluster.redis.scan_iter(
            self.cluster.get_redis_key(WORKER_KEY.format('*'))
            ):
            data.append(await self.get_worker_data_from_redis(each))
        return data
    
    async def get_remote_worker_data(self, worker_id):
        return await self.get_worker_data_from_redis(
            self.cluster.get_redis_key(WORKER_KEY.format(worker_id)
        ))

    def load_serving_engines(self, engines: list):
        for each in engines:
            engine_module = __import__(each,fromlist=[each])
            if not issubclass(engine_module.ServingEngine, ServingEngine):
                raise ValueError("Invalid ServingEngine ",each)
            engine_instance = engine_module.ServingEngine()
            engine_instance.validate_engine_options()
            self.serving_engines[engine_module.__name__] = engine_instance
        logging.info("available serving engines: %s",",".join(self.serving_engines))

    def load_storage_engines(self, engines: list):
        for each in engines:
            engine_module = __import__(each,fromlist=[each])
            if not issubclass(engine_module.StorageEngine, StorageEngine):
                raise ValueError("Invalid StorageEngine ",each)
            engine_instance = engine_module.StorageEngine()
            engine_instance.validate_engine_options()
            self.storage_engines[engine_module.__name__] = engine_instance
        logging.info("available storages engines: %s",",".join(self.storage_engines))
    
    async def shutdown(self, sig, loop):
        logging.info("Shutting down gracefully, reson=%s",sig)
        self.state = "shutting_down"
        await self.report_once(send_events=True)

        self.shutdown_requested = True
        self.scheduler.shutdown_requested = True

        logging.info("watting for worker_pubsub_task")
        await self.worker_pubsub_task
        logging.info("watting for report_forever")
        await self.report_forever_task
        logging.info("waitting for scheduler")
        await self.scheduler_task
        logging.info("waitting for scheduler_pubsub_task")
        await self.scheduler_pubsub_task
        logging.info("Shutting down gracefully Completed")
    

    async def _get_model_instance_from_event_data(self, event_data):
        if(event_data["worker_id"]!=self.id):
            logging.error("worker_id missmatch, expected %s found %s", self.id, event_data["worker_id"])
            return
        namespace = ModelNamespace(cluster=self.cluster, id=event_data["namespace_id"])
        try:
            await namespace.read()
        except exceptions.NotFoundException:
            return
        model = Model(namespace=namespace, id=event_data["model_id"])
        try:
            await model.read()
        except exceptions.NotFoundException:
            return
        model_version = ModelVersion(model=model, id=event_data["model_version_id"])
        try:
            await model_version.read()
        except exceptions.NotFoundException:
            return
        model_instance = ModelInstance(model_version, id=event_data["model_instance_id"])
        try:
            await model_instance.read()
        except exceptions.NotFoundException:
            return
        return model_instance

    async def handle_model_instance_scheduled(self, event_data):
        model_instance = await self._get_model_instance_from_event_data(event_data)
        await self.activate_model_instance(model_instance)
    
    async def handle_terminate_model_instance(self, event_data):
        model_instance = await self._get_model_instance_from_event_data(event_data)
        local_model_instance = self.local_model_instances[model_instance.redis_key]
        await self.deactivate_model_instance(local_model_instance)
    


    async def channel_reader(self):
        while not self.shutdown_requested:
            message = None
            try:
                async with async_timeout.timeout(1):
                    message = await self.worker_pubsub.get_message(ignore_subscribe_messages=True)
                    await asyncio.sleep(0.01)
            except asyncio.TimeoutError:
                pass
            if message is not None:
                logging.debug(f"(Worker Reader) Message Received: {message}")
                data = json.loads(message["data"])
                if data["event_type"] == "MODEL_INSTANCE_SCHEDULED":
                    await self.handle_model_instance_scheduled(data["event_data"])
                elif data["event_type"] == "TERMINATE_MODEL_INSTANCE":
                    await self.handle_terminate_model_instance(data["event_data"])
                else:
                    logging.info("Unknown event type %s, skipping", data["event_type"])
    
    async def activate_model_instance(self, model_instance: ModelInstance):
        ns = model_instance.model.namespace
        storage_engine = self.storage_engines[ns.settings["storage_engine"]]
        serving_engine = self.serving_engines[ns.settings["serving_engine"]]
        model_parameters = model_instance.model_version.parameters

        loop = asyncio.get_event_loop()

        model_instance.state = "initializing"
        await model_instance.save()
        await self.register_local_model_instance(model_instance)

        try:
            await loop.run_in_executor(None, partial(storage_engine.validate_model_parameters,
                model_parameters=model_parameters))
        except Exception as e:
            model_instance.state = "fetch_validation_error"
            model_instance.error_messages = [str(e)]
            await model_instance.save()
            await self.register_local_model_instance(model_instance)
            return
        storage_context = None
        try:
            storage_context = await loop.run_in_executor(None, partial(storage_engine.fetch_model,
            model_parameters=model_parameters))
        except Exception as e:
            model_instance.state = "fetch_error"
            model_instance.error_messages = [str(e)]
            await model_instance.save()
            await self.register_local_model_instance(model_instance)
            return
        model_instance.state = "loadding"
        model_instance.storage_context = storage_context
        await model_instance.save()
        await self.register_local_model_instance(model_instance)

        try:
            await loop.run_in_executor(None, partial(serving_engine.validate_model_parameters,
                model_parameters=model_parameters))
        except Exception as e:
            model_instance.state = "load_model_validation_error"
            model_instance.error_messages = [str(e)]
            await model_instance.save()
            await self.register_local_model_instance(model_instance)
            return
        serving_context = None
        worker_serving_context = None
        try:
            serving_context, worker_serving_context  = await loop.run_in_executor(None, partial(serving_engine.load_model,
            model_parameters=model_parameters,
            storage_context=storage_context)
            )
        except Exception as e:
            model_instance.state = "load_model_error"
            model_instance.error_messages = [str(e)]
            await model_instance.save()
            await self.register_local_model_instance(model_instance)
            return
        model_instance.state = "serving"
        model_instance.storage_context = storage_context
        model_instance.serving_context = serving_context
        model_instance.worker_serving_context = worker_serving_context
        await model_instance.save()
        await self.register_local_model_instance(model_instance)
    
    async def deactivate_model_instance(self, model_instance: ModelInstance):
        ns = model_instance.model.namespace
        model_parameters = model_instance.model_version.parameters

        storage_engine = self.storage_engines[ns.settings["storage_engine"]]
        serving_engine = self.serving_engines[ns.settings["serving_engine"]]

        loop = asyncio.get_event_loop()

        logging.debug("terminating model instance id=%s model_id=%s version=%s namespace=%s",
            model_instance.id, model_instance.model.id, model_instance.model_version_id, model_instance.model.namespace.id)
        model_instance.state = "terminating"
        await model_instance.save()
        await self.report_once(send_events=True)
        try:
            await loop.run_in_executor(None, partial(serving_engine.unload_model,
            model_parameters=model_parameters,
            storage_context=model_instance.storage_context,
            serving_context=model_instance.serving_context,
            worker_serving_context=model_instance.worker_serving_context
            ))
        except Exception as e:
            logging.exception(e)
            logging.error("error unloading model")
        try:
            await loop.run_in_executor(None, partial(storage_engine.clean_model,
            model_parameters=model_parameters,
            storage_context=model_instance.storage_context
            ))
        except Exception as e:
            logging.exception(e)
            logging.error("error cleaning storage for model")
        
        await self.deregister_local_model_instance(model_instance)

    
    async def register_local_model_instance(self, model_instance:ModelInstance):
        self.local_model_instances[model_instance.redis_key] = model_instance
        await self.report_once(send_events=True)
    
    async def deregister_local_model_instance(self, model_instance:ModelInstance):
        try:
            del self.local_model_instances[model_instance.redis_key]
        except KeyError:
            pass
        await self.report_once(send_events=True)
    
    async def apply_worker_annotators(self):
        annotations = {}
        for each in WORKER_ANNOTATORS:
            annotations.update(await each(self))
        self.serving_endpoint = annotations.get("serving_endpoint")

    async def run_forever(self):
        from .scheduler import Scheduler
        
        await self.apply_worker_annotators()

        management_api_runner = web.AppRunner(management_api.app)
        management_api.context_worker.set(self)
        await management_api_runner.setup()
        management_api_site = web.TCPSite(management_api_runner,
            self.options.management_host, self.options.management_port)
        await management_api_site.start()
        logging.info("Management API started, host=%s port=%d",self.options.management_host, self.options.management_port)

        serving_api_runner = web.AppRunner(serving_api.app)
        serving_api.context_worker.set(self)
        await serving_api_runner.setup()
        serving_api_site = web.TCPSite(serving_api_runner,
            self.options.serving_host, self.options.serving_port)
        await serving_api_site.start()
        logging.info("Serving API started, host=%s port=%d",self.options.serving_host, self.options.serving_port)

        loop = asyncio.get_event_loop()

        self.state = "initializing"
        await self.report_once(send_events=True)
        self.report_forever_task = loop.create_task(self.report_forever())
        await loop.run_in_executor(None, self.load_storage_engines, self.options.storage_engines)
        await loop.run_in_executor(None, self.load_serving_engines, self.options.serving_engines)
        
        self.state = "serving"
        await self.report_once(send_events=True)

        self.worker_pubsub = self.cluster.redis.pubsub()
        await self.worker_pubsub.subscribe(
            self.cluster.get_redis_channel_key(self.worker_key)
            )

        self.worker_pubsub_task = loop.create_task(self.channel_reader())
        self.scheduler = Scheduler(cluster=self.cluster, worker=self)
        self.scheduler_task = loop.create_task(self.scheduler.schedule_forever())
        self.scheduler_pubsub_task = loop.create_task(await self.scheduler.setup_pubsub())

        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
            s, lambda s=s: asyncio.create_task(self.shutdown(s, loop)))

        await asyncio.gather(
            self.report_forever_task,
            self.scheduler_task,
            self.worker_pubsub_task,
            self.scheduler_pubsub_task
        )
    
    async def do_infer(self, model_instance:ModelInstance, data: dict):
        local_instance = self.local_model_instances[model_instance.redis_key]
        ns = local_instance.model.namespace
        serving_engine = self.serving_engines[ns.settings["serving_engine"]]
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(serving_engine.infer,
            model_parameters=local_instance.model_version.parameters,
            storage_context=local_instance.storage_context,
            serving_context=local_instance.serving_context,
            worker_serving_context=local_instance.worker_serving_context,
            data=deepcopy(data))
            )