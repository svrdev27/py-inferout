import logging
from aiohttp import web
import contextvars

from . import models
from . import exceptions

context_worker = contextvars.ContextVar('worker')


async def index(request):
    worker = context_worker.get()
    return web.json_response({
            "service": "Inferout Management API",
            "cluster_name": worker.cluster.name,
            "cluster_version": worker.cluster.version,
            "redis_key_prefix": worker.cluster.redis_key_prefix,
            "current_worker_id": worker.id
        }
        )

async def workers(request):
    worker = context_worker.get()
    return web.json_response({
            "workers" : await worker.get_all_workers_data()
        }
        )

async def namespaces(request):
    worker = context_worker.get()
    return web.json_response({
        "namespaces": await models.ModelNamespace.get_all_as_list(worker.cluster)
    })

async def namespace_get(request):
    worker = context_worker.get()

    id = request.match_info.get('id')
    ns = models.ModelNamespace(cluster=worker.cluster, id=id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    return web.json_response({
        "id": ns.id,
        "settings": ns.settings
    })

async def namespace_put(request):
    worker = context_worker.get()

    id = request.match_info.get('id')
    request_data = await request.json()
    ns = models.ModelNamespace(cluster=worker.cluster, id=id)
    ns.settings = request_data.get('settings')
    logging.info(request_data)
    await ns.save()
    return web.json_response({
        "id": ns.id,
        "settings": ns.settings
    })

async def model_get(request):
    worker = context_worker.get()

    id = request.match_info.get('id')
    namespace_id = request.match_info.get('namespace_id')

    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    model = models.Model(namespace=ns, id=id)
    try:
        await model.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    return web.json_response({
        "id": model.id,
        "parameters": model.parameters,
        "latest_version_id": model.latest_version_id
    })

async def model_put(request):
    worker = context_worker.get()

    id = request.match_info.get('id')
    namespace_id = request.match_info.get('namespace_id')
    request_data = await request.json()
    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound

    model = models.Model(namespace=ns, id=id)
    try:
        await model.read()
    except exceptions.NotFoundException:#updating
        pass
    model.parameters = request_data.get('parameters', {})
    try:
        await model.save()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    return web.json_response({
        "id": model.id,
        "parameters": model.parameters,
        "latest_version_id": model.latest_version_id
    })

async def models_index(request):
    worker = context_worker.get()
    namespace_id = request.match_info.get('namespace_id')

    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound

    return web.json_response({
        "models": await models.Model.get_all_as_list(worker.cluster, ns)
    })

async def model_versions_index(request):
    worker = context_worker.get()
    namespace_id = request.match_info.get('namespace_id')
    model_id = request.match_info.get('model_id')

    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    
    model = models.Model(namespace=ns, id=model_id)
    try:
        await model.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound

    return web.json_response({
        "model_versions": await models.ModelVersion.get_all_as_list(worker.cluster, model)
    })

async def model_instances_index(request):
    worker = context_worker.get()
    namespace_id = request.match_info.get('namespace_id')
    model_id = request.match_info.get('model_id')

    ns = models.ModelNamespace(cluster=worker.cluster, id=namespace_id)
    try:
        await ns.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound
    
    model = models.Model(namespace=ns, id=model_id)
    try:
        await model.read()
    except exceptions.NotFoundException:
        raise web.HTTPNotFound

    return web.json_response({
        "model_instances": await models.ModelInstance.get_all_as_list(worker.cluster, model)
    })

app = web.Application()
app.add_routes([
    web.get('/', index),
    web.get('/workers', workers),
    web.get('/namespaces', namespaces),
    web.get('/namespaces/{id}', namespace_get),
    web.put('/namespaces/{id}', namespace_put),
    web.get('/namespaces/{namespace_id}/models', models_index),
    web.get('/namespaces/{namespace_id}/models/{id}', model_get),
    web.put('/namespaces/{namespace_id}/models/{id}', model_put),
    web.get('/namespaces/{namespace_id}/models/{model_id}/versions', model_versions_index),
    web.get('/namespaces/{namespace_id}/models/{model_id}/instances', model_instances_index)
])