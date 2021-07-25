from .worker import Worker
from .cluster import Cluster
import configargparse
import aioredis
import asyncio
import logging

async def main(options):
    redis = await aioredis.from_url(
        options.redis_url,
        encoding="utf-8",
        decode_responses=True)
    command = options.command
    cluster = Cluster(redis=redis,
        redis_key_prefix=options.redis_key_prefix,
        name=options.cluster_name)

    if command == "bootstrap_cluster":
        await cluster.bootstrap()
    elif command == "worker":
        await cluster.sync()
        logging.info("Joinning Cluster: name=%s version=%s", cluster.name, cluster.version)
        worker = Worker(cluster=cluster, options=options)
        await worker.run_forever()

def setup_logging(options):
    logging.basicConfig(
        level=getattr(logging,options.log_level),
        #format='%(asctime)s | %(name)s | [%(pathname)s %(funcName)s %(lineno)d] | %(levelname)s | %(message)s'
        )

def execute_from_command_line(argv=None):
    p = configargparse.ArgParser()
    p.add('command', choices=["bootstrap_cluster", "worker"], help='command')
    p.add('--cluster-name', required=True, help='name of the cluster')
    p.add('--redis-url', required=True, help='redis url')
    p.add('--redis-key-prefix', default="inferout", help='key prefix used for redis keys')
    p.add('--log-level', default="INFO", choices=["DEBUG","INFO","WARNING"], help='Logging Level')
    p.add('--management-host', default="0.0.0.0", help='listen host for management API')
    p.add('--management-port', default="9500", help='listen port for management API', type=int)
    p.add('--serving-host', default="0.0.0.0", help='listen host for serving API')
    p.add('--serving-port', default="9510", help='listen port for serving API', type=int)

    p.add('--storage-engines', nargs='+', default=['inferout.storage_engines.local_files'])
    p.add('--serving-engines', nargs='+', default=['inferout.serving_engines.echo'])
    options, _unknown = p.parse_known_args()
    setup_logging(options)
    asyncio.run(main(options))    