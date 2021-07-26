from inferout.storage_engines import base
import configargparse
import os
import shutil
import tempfile
import random
import string

def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

def get_temp_dir_name():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

class StorageEngine(base.StorageEngine):
    def __init__(self) -> None:
        pass
    
    def validate_engine_options(self):
        p = configargparse.ArgParser()

        p.add('--my-rasa-nlu-store-dir', default='/tmp/nlu_models', type=dir_path, help='Directory location for NLU models')
        p.add('--my-rasa-nlu-temp-dir', default='/tmp/temp_nlu_models', type=dir_path, help='Directory location for NLU models')
        options, _unknown = p.parse_known_args()
        self.base_dir = options.my_rasa_nlu_store_dir
        self.temp_dir = options.my_rasa_nlu_temp_dir
    
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
        temp_dir = os.path.join(self.temp_dir, get_temp_dir_name())
        os.mkdir(temp_dir)
        shutil.unpack_archive(final_path, temp_dir)
        return {"local_path": temp_dir}
        
    def clean_model(self, model_parameters:dict, storage_context:dict):
        shutil.rmtree(storage_context["local_path"])