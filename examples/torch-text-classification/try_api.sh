cp my_text_classification/model.tar.gz /tmp/inferout_models
cd /tmp/inferout_models
tar -xvf model.tar.gz

curl -XPUT localhost:9500/namespaces/torch_text -d '{"settings":{"instances_per_model":{"min":1,"max":2,"target":1},"serving_engine":"my_text_classification.serving_engine"}}'
curl -XPUT localhost:9500/namespaces/torch_text/models/mymodel1 -d '{"parameters":{"path":"model"}}'
curl -XPOST localhost:9510/torch_text/mymodel1 -d '{"input_data":{"query":"Hay"}}'
