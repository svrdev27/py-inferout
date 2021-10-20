from . import base
import os

class Plugin(base.Plugin):
    def __init__(self) -> None:
        pass

    def load(self) -> None:
        self.pod_ip = os.environ["POD_IP"]
        self.pod_name = os.environ["POD_NAME"]
        self.pod_region = os.environ.get("POD_REGION") or ""
        self.pod_zone = os.environ.get("POD_ZONE") or ""
        self.k8s_rack = "-".join(filter(None, [self.pod_region,self.pod_zone]))
        if not self.k8s_rack:
            self.k8s_rack = os.environ["HOST_IP"]
        

    def get_management_host(self) -> str:
        return self.pod_ip
    
    def get_serving_host(self) -> str:
        return self.pod_ip
    
    def get_rack_format(self) -> str:
        return "{k8s_rack}"
    
    def get_worker_attributes(self) -> map:
        return {
            "pod_ip": self.pod_ip,
            "pod_name": self.pod_name,
            "pod_region": self.pod_region,
            "pod_zone": self.pod_zone,
            "k8s_rack": self.k8s_rack
            }