import uuid
import base64
import collections.abc

def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def get_redis_key(*args) -> str:
    return "::".join(args)

def split_redis_key(key) -> list:
    return key.split("::")


def get_uuid_as_string() -> str:
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('ascii')

def covert_to_redis_slot(key:str) -> str:
    return "{{{}}}".format(key)
