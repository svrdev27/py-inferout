# py-inferout
Distributed Scale Out Framework for ML model serving/inferencing

**This Project is in development, Not intended for production use**

### Install
It is available in PyPI
```console
$ pip install inferout
```
if you don't have pip command use -m pip
```console
$ python -m pip install inferout
```

### Usage (Quick example)
- First of all we need an ml model to be able to serve. It can be of any kind, any framework (pytorch, tensorflow, rasa, etc.) as long as it can be loaded in python 3.7+
- We need to implement two interfaces
  - serving_engine - this is to teach inferout how to load, serve (infer), and unload the models of a specific kind/usecase. [example](examples/rasa-nlu/my_rasa_nlu/serving_engine.py)
  - storage_engine - this is to teach inferout how to get/download/locate the models. [example](examples/rasa-nlu/my_rasa_nlu/storage_engine.py)
- Get redis server ready. Yes we need redis to use inferout. inferout uses redis to store metadata and pass messages between diferent componets and nodes. https://redis.io/download
- Bootstrap cluster - this is create minimum metadata required to run cluster all you need is a cluster name and a redis URL
  ```console
  $ inferout bootstrap_cluster --cluster-name my_rasa_nlu --redis-url redis:///10
  ```

- Launch the worker
  ```console
  $ inferout worker --cluster-name my_rasa_nlu --redis-url redis:///10 --storage-engines "my_rasa_nlu.storage_engine" --serving-engines "my_rasa_nlu.serving_engine"
  ```
  Can run multiple workers for single cluster. to run multiple workers in single system (for development and to test) we can use diferent port numbers for each worker. try "inferout worker -h" for more details
  
  What we need to make sure is worker availabily and connectivity(serving api port) between nodes else(replication of models and distributing to workers, smartly routing the inferencing requests) will be taken care by inferout framework.
  
- Create namespace
  ```console
  $ curl -XPUT localhost:9500/namespaces/default -d '{"settings":{"storage_engine":"my_rasa_nlu.storage_engine","serving_engine":"my_rasa_nlu.serving_engine"}}'
  ```
- Create model
  ```console
  $ curl -XPUT localhost:9500/namespaces/default/models/mymodel1 -d '{"parameters":{"path":"nlu-20210726-153112.tar.gz"}}'
  ```
  wondering how to get this model file and where to place it for testing?
  install open source rasa using pip. https://rasa.com/docs/rasa/installation
  ```console
  $ pip3 install rasa
  ```
  init rasa project
  ```console
  $ rasa init
  ```
  train your nlu model
  ```console
  $ rasa train nlu
  ```
  make required directories and copy the model
  ```console
  $ mkdir /tmp/nlu_models
  $ mkdir /temp_nlu_models
  $ ls models
  $ cp models/nlu-*.tar.gz /tmp/nlu_models/
  ```
  
- Query your model (inference)
  ```console
  $ curl -XPOST localhost:9510/default/mymodel1 -d '{"input_data":{"query":"Hi"}}'
  ```
  Did you find any change in port number? Yes for namespace and model creation we used 9500 but now we used 9510
  inferout worker provides 2 API services
  - management API - create/update/delete/inspect models, namespaces, workers
  - inferencing API - to quiry models
- What next?
  Explore other management APIs, for now just find API endpoints in [source code](inferout/management_api.py#L170)
  
