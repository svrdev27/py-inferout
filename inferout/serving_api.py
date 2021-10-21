import json
import logging
from aiohttp import web
import contextvars
import random

import aiohttp

from . import models
from . import exceptions

context_worker = contextvars.ContextVar('worker')


async def index(request):
    worker = context_worker.get()

    return web.json_response({
            "service": "Inferout Serving API",
            "cluster_name": worker.cluster.name,
            "cluster_version": worker.cluster.version,
            "redis_key_prefix": worker.cluster.redis_key_prefix,
            "current_worker_id": worker.id
        }
        )

async def handle_infer_post(request):
    worker = context_worker.get()
    namespace_id = request.match_info.get('namespace_id')
    model_id = request.match_info.get('model_id')
    version_id = request.match_info.get('version_id')

    try:
        request_data = await request.json()
    except json.decoder.JSONDecodeError:
        raise web.HTTPBadRequest(text="Invalid JSON")
        
    input_data = request_data.get("input_data") or {}

    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound

    model = models.Model(namespace=ns, id=model_id)
    try:
        await model.read()
    except exceptions.NotFoundException:#updating
        pass
    
    version = None
    if version_id in ("_latest", "latest"):
        version = models.ModelVersion(model=model, id=str(model.latest_version_id))
    elif version_id in (None, "", "any", "_latest_available"):
        version = None
    else:
        version = models.ModelVersion(model=model, id=version_id)
    if version is not None:
        try:
            await version.read()
        except exceptions.NotFoundException:#updating
            pass

    instances_data = await models.ModelInstance.get_all_as_list(
        cluster=worker.cluster,
        model=model,
        version=version)
    
    instances_data = list(filter(lambda x: x["state"]=="serving", instances_data))

    output_data = None

    try:
        local_instance_data = list(filter(lambda x: x["worker_id"]==worker.id, instances_data))[0]
    except IndexError:
        local_instance_data = None

    
    if local_instance_data:
        logging.info("Serving from local worker")
        if version is None:
            version = models.ModelVersion(model=model, id=local_instance_data["model_version_id"])
            try:
                await version.read()
            except exceptions.NotFoundException:#updating
                pass
        instance = models.ModelInstance(model_version=version,id=local_instance_data["id"])
        output_data = await worker.do_infer(model_instance=instance, data=input_data)
        return web.json_response({
            "model_version": version.id,
            "worker_id": local_instance_data["worker_id"],
            "input_data": input_data,
            "output_data": output_data
            })
    else:
        random.shuffle(instances_data)
        for each in instances_data:
            remote_worker_data = await worker.get_remote_worker_data(worker_id=each["worker_id"])
            logging.info("Routing to remote worker id=%s endpoint=%s",
                remote_worker_data["id"], remote_worker_data["serving_endpoint"])
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    remote_worker_data["serving_endpoint"]+request.path_qs,
                    json=request_data) as response:
                    response_data = await response.json()
                    return web.json_response(response_data)
        
        logging.error("No active Model Instances found")
        raise web.HTTPServiceUnavailable

app = web.Application()
app.add_routes([
    web.get('/', index),
    web.post('/{namespace_id}/{model_id}', handle_infer_post),
    web.post('/{namespace_id}/{model_id}/{version_id}', handle_infer_post),
    ])