from inferout.serving_engines import base
from typing import Tuple
import configargparse
from .models import (TextClassificationModel,
ag_news_label,
text_pipeline,
predict
)
import os
import json
import torch


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
        meta = json.loads(open(os.path.join(storage_context['local_path'],"meta.json")).read())
        model = TextClassificationModel(*meta["model_params"])
        model.load_state_dict(torch.load(os.path.join(storage_context['local_path'],"model.torch")))
        serving_context = {"model_meta": meta}
        worker_serving_context = {"torch_model": model}
        return (serving_context, worker_serving_context)
    
    def unload_model(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict):
        pass

    def infer(self, model_parameters:dict, storage_context:dict, serving_context: dict, worker_serving_context:dict, data: dict) -> dict:
        query = data.get("query") or ""
        model = worker_serving_context["torch_model"]
        result = ag_news_label.get(predict(model, query))
        return {"label": result}
