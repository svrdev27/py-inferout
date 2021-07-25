class StorageEngine(object):
    def __init__(self) -> None:
        raise NotImplementedError()
    
    def validate_engine_options(self):
        raise NotImplementedError()
    
    def prepare(self):
        raise NotImplementedError()
    
    def validate_model_parameters(self, model_parameters):
        raise NotImplementedError()
    
    def fetch_model(self, model_parameters) -> dict:#returns model fetch_context
        raise NotImplementedError()
    
    def clean_model(self, model_parameters:dict, storage_context:dict):
        raise NotImplementedError()