

import yaml

stream = open("/home/erm/.ipfs-feed-translator/config.yml", "r")
docs = yaml.load_all(stream)

for doc in docs:
    for k,v in doc.items():
        print (k, "->", v)