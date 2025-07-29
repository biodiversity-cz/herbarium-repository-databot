# herbarium-repository-databot
Databots for herbarium repository. Use Databot name as argument to run it immediately or all will be regularly proceeded via crontable.

## local run
```shell
poetry env use python3.13
poetry install

poetry run python main.py connection_tester
poetry run python main.py 
```

or with docker:

docker build -t mybot .
docker run --rm  mybot connection_tester
docker run --network="host" mybot connection_tester
