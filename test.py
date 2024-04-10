import os
import typing

import eodag

os.environ[
    "EODAG__DE_DT_LUMI__AUTH__CREDENTIALS__USERNAME"
] = "aubin.lambare@csgroup.eu"
os.environ[
    "EODAG__DE_DT_LUMI__AUTH__CREDENTIALS__PASSWORD"
] = "d3ae802130fa23fb43c48a2e88d374bb"

dag = eodag.EODataAccessGateway()

eodag.setup_logging(3)

results, total = dag.search(
    productType="DT_EXTREMES", start="2024-04-01T00:00:00Z", param=31
)

results, total = dag.search(
    productType="DT_CLIMATE_ADAPTATION", start="2024-04-01T00:00:00Z", param=34
)

product = typing.cast(eodag.EOProduct, results[0])

path = product.download(wait=0.1)

print(path)
