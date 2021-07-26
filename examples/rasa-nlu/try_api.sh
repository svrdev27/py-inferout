curl -XPUT localhost:9500/namespaces/default -d '{"settings":{"storage_engine":"my_rasa_nlu.storage_engine","serving_engine":"my_rasa_nlu.serving_engine"}}'
curl -XPUT localhost:9500/namespaces/default/models/mymodel1 -d '{"parameters":{"path":"nlu-20210726-153112.tar.gz"}}'
curl -XPOST localhost:9510/default/mymodel1 -d '{"input_data":{"query":"Hi"}}'
