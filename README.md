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

[//]: # (obligatory branding for EOSC.CZ)
<hr style="margin-top: 100px; margin-bottom: 20px">

<p style="text-align: left"> <img src="https://webcentrum.muni.cz/media/3831863/seda_eosc.png" alt="EOSC CZ Logo" height="90"> </p>
This project output was developed with financial contributions from the EOSC CZ initiative throught the project National Repository Platform for Research Data (CZ.02.01.01/00/23_014/0008787) funded by Programme Johannes Amos Comenius (P JAC) of the Ministry of Education, Youth and Sports of the Czech Republic (MEYS).

<p style="text-align: left"> <img src="https://webcentrum.muni.cz/media/3832168/seda_eu-msmt_eng.png" alt="EU and MŠMT Logos" height="90"> </p>
