# herbarium-repository-databot
Databots for herbarium repository. Use Databot name as argument to run it immediately or all will be regularly proceeded via crontable.

## local run
```shell
poetry env use python3.13
poetry install

poetry run python main.py database_connection_tester
poetry run python main.py no-ref-image-metrics
poetry run python main.py 
```

or with docker:

docker build -t databots .
docker run --rm  databots no-ref-image-metrics
docker run --network="host" databots connection_tester
