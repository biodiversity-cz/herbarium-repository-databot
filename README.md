# herbarium-repository-databot
Databots for herbarium repository

## local run
```shell
poetry env use python3.13
poetry install

poetry run python main.py bot1
```

or with docker:

docker build -t mybot .
docker run --rm -e DB_HOST=... -e DB_NAME=... -e DB_USER=... -e DB_PASS=... mybot bot1
docker run --network="host" mybot bot1
