from inferout.models import ModelInstance
from typing import Tuple
from inferout import worker
import re
from . import base
import configargparse
import os


class EchoInstance(object):
    def __init__(self, lines) -> None:
        self.tokens = "\n".join(lines).split()

class ServingEngine(base.ServingEngine):
    def __init__(self) -> None:
        pass
    
    def validate_engine_options(self):
        p = configargparse.ArgParser()

        p.add('--echo-serving-file-name', type=str, help='example value')
        options, _unknown = p.parse_known_args()
        self.file_name = options.echo_serving_file_name
    
    def prepare(self):
        pass
    
    def validate_model_parameters(self, model_parameters):
        allow_echo = model_parameters.get("allow_echo")
        file_name = model_parameters.get("file_name") or self.file_name
        if not allow_echo:
            raise ValueError("allow_echo is required")
        if not file_name:
            raise ValueError("file_name is required")
    
    def load_model(self, model_parameters:dict, storage_context:dict) -> Tuple[dict, dict]:
        file_name = model_parameters.get("file_name") or self.file_name
        file_path = os.path.join(storage_context["local_path"], file_name)
        text_lines = open(file_path, 'r').readlines()
        echo_instance = EchoInstance(lines=text_lines)
        serving_context = {"echo_model_loaded": True}
        worker_serving_context = {"text_lines": text_lines, "echo_instance": echo_instance}
        return (serving_context, worker_serving_context)
        
    def unload_model(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict):
        del worker_serving_context["echo_instance"].tokens
    
    def infer(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict, data: dict) -> dict:
        data["tokens"] = worker_serving_context["echo_instance"].tokens
        return data