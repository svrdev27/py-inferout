from . import base
import configargparse
import os


def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

class StorageEngine(base.StorageEngine):
    def __init__(self) -> None:
        pass
    
    def validate_engine_options(self):
        p = configargparse.ArgParser()

        p.add('--local-files-store-dir', default='/tmp/infer_models', type=dir_path, help='Directory location for local_files store')
        options, _unknown = p.parse_known_args()
        self.base_dir = options.local_files_store_dir
    
    def prepare(self):
        pass
    
    def validate_model_parameters(self, model_parameters):
        if not model_parameters.get("path"):
            raise ValueError("Path is required")
        final_path = os.path.join(self.base_dir, model_parameters.get("path"))
        if not os.path.exists(final_path):
            raise ValueError("Does Not exist:", final_path)

    
    def fetch_model(self, model_parameters) -> dict:
        final_path = os.path.join(self.base_dir, model_parameters["path"])
        return {"local_path": final_path}
        
    def clean_model(self, model_parameters:dict, storage_context:dict):
        pass