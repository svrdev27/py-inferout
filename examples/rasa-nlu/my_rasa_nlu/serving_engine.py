from inferout.serving_engines import base
from typing import Tuple
import configargparse

from rasa.nlu.model import Interpreter
import os

class ServingEngine(base.ServingEngine):
    def __init__(self) -> None:
        pass

    def validate_engine_options(self):
        pass

    def prepare(self):
        pass

    def validate_model_parameters(self, model_parameters):
        pass

    def load_model(self, model_parameters:dict, storage_context:dict) -> Tuple[dict, dict]:
        interpreter = Interpreter.load(os.path.join(storage_context['local_path'],'nlu'))
        serving_context = {}
        worker_serving_context = {"interpreter": interpreter}
        return (serving_context, worker_serving_context)
    
    def unload_model(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict):
        pass

    def infer(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict, data: dict) -> dict:
        query = data.get("query") or ""
        result = worker_serving_context["interpreter"].parse(query)
        return {'intent': result.get('intent'), 'entities': result.get('entities')}

