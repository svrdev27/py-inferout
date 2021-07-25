from typing import Tuple


class ServingEngine(object):
    def __init__(self) -> None:
        raise NotImplementedError()
    
    def validate_engine_options(self):
        raise NotImplementedError()
    
    def prepare(self):
        raise NotImplementedError()
    
    def validate_model_parameters(self, model_parameters:dict):
        raise NotImplementedError()
    
    def load_model(self, model_parameters:dict, storage_context:dict) -> Tuple[dict, dict]:#load_context
        raise NotImplementedError()
    
    def unload_model(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict):
        raise NotImplementedError()
    
    def infer(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict, data: dict) -> dict:
        raise NotImplementedError()