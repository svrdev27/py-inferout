async def serving_endpoint_from_options(worker):
    host = worker.options.serving_host
    port = worker.options.serving_port
    endpoint = "http://{host}:{port}".format(host=host,port=port)
    return {"serving_endpoint": endpoint}