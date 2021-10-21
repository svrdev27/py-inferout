from inferout.storage_engines import base
import configargparse
import os
import shutil
import tempfile
import random
import string
import boto3
import urllib.parse

def dir_path(string):
    if os.path.isdir(string):
        return string
    else:
        raise NotADirectoryError(string)

def get_temp_dir_name():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

class StorageEngine(base.StorageEngine):
    def __init__(self) -> None:
        self.s3_client = boto3.client('s3')

    def validate_engine_options(self):
        p = configargparse.ArgParser()

        p.add('--storage-aws-s3-local-temp-dir', default='/tmp', type=dir_path, help='Directory location for keeping models in local')
        options, _unknown = p.parse_known_args()
        self.temp_dir = options.storage_aws_s3_local_temp_dir
    
    def prepare(self):
        pass
    
    def validate_model_parameters(self, model_parameters):
        if not model_parameters.get("storage_aws_s3_url"):
            raise ValueError("storage_aws_s3_url is required")
        url = urllib.parse.urlparse(model_parameters.get("storage_aws_s3_url"))
        if url.scheme.lower()!="s3" or not url.hostname or not url.path:
            raise ValueError("invalid s3 url "+model_parameters.get("storage_aws_s3_url"))
    
    def fetch_model(self, model_parameters) -> dict:
        s3_url_parts = urllib.parse.urlparse(model_parameters.get("storage_aws_s3_url"))
        temp_dir = os.path.join(self.temp_dir, get_temp_dir_name())
        os.mkdir(temp_dir)
        file_name = os.path.split(s3_url_parts.path)[-1]
        final_path = os.path.join(temp_dir,file_name)
        self.s3_client.download_file(s3_url_parts.hostname,s3_url_parts.path[1:],final_path)
        if model_parameters.get("storage_aws_s3_unpack_archive"):
            temp_dir = os.path.join(self.temp_dir, get_temp_dir_name())
            os.mkdir(temp_dir)
            shutil.unpack_archive(final_path, temp_dir)
            final_path = temp_dir
        return {"local_path": final_path}
        
    def clean_model(self, model_parameters:dict, storage_context:dict):
        shutil.rmtree(storage_context["local_path"])