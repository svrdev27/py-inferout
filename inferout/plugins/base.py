class Plugin(object):
    def __init__(self) -> None:
        raise NotImplementedError()

    def load(self) -> None:
        raise NotImplementedError()

    def get_management_host(self) -> str:
        raise NotImplementedError()
    
    def get_management_port(self) -> int:
        raise NotImplementedError()
    
    def get_serving_host(self) -> str:
        raise NotImplementedError()
    
    def get_serving_port(self) -> int:
        raise NotImplementedError()
    
    def get_rack_format(self) -> str:
        raise NotImplementedError()
    
    def get_worker_attributes(self) -> map:
        raise NotImplementedError()