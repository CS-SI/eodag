import requests

from eodag import EODataAccessGateway
from eodag.utils.logging import setup_logging

# from eodag.plugins.download import session_http

setup_logging(3)

dag = EODataAccessGateway()

# product_types = dag.list_product_types("ssalto")
product_types = dag.list_product_types(provider="earthdata_lars_asdc")
# product_types = dag.list_product_types(provider="earthdata_obdaac")
# product_types = dag.list_product_types(provider="earthdata_podaac")
# product_types = dag.list_product_types(provider="cop_dataspace_s3")
product_types
# id = [pt["ID"] for pt in product_types]
# id

# SEARCH

# products = dag.search(
#     productType="a6efcb0868664248b9cb212aba44313d",
#     provider="fedeo_ceda",
#     )
# products = dag.search(
#     productType="AATSR_ENS_L2_V2.6",
#     provider="fedeo_ceda",
#     format="netCDF",
# )
products = dag.search(
    provider="earthdata_lars_asdc",
    productType='ACTIVATE-FLEXPART_1',
)
# products = dag.search(
#     provider="earthdata_podaac",
#     productType='OPERA_L3_DSWX-S1_V1_1.0',
# )
# products = dag.search(
#     provider="earthdata_obdaac",
#     productType='Chesapeake_Bay_Water_Quality_0',
# )
# products = dag.search(
#     provider="cop_dataspace_s3",
#     productType="S1_SAR_GRD",
# )
products

# for product in products:
#     print(product.properties.get("platformSerialIdentifier"))


# DOWNLOAD
first_product = products[1]

dag.download(first_product, output_dir="/home/tlarrouy/eodag/download")

# paths = dag.download_all(products, output_dir="/home/tlarrouy/eodag/download")
# paths


# apikey: eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6InRsYXJyb3V5IiwiZXhwIjoxNzYxNTIzMTk5LCJpYXQiOjE3NTYyODYxOTUsImlzcyI6Imh0dHBzOi8vdXJzLmVhcnRoZGF0YS5uYXNhLmdvdiIsImlkZW50aXR5X3Byb3ZpZGVyIjoiZWRsX29wcyIsImFjciI6ImVkbCIsImFzc3VyYW5jZV9sZXZlbCI6M30.UpiLkHdfPnhJkmcaTWTcmyQl_w1vvrIJ1Cs7tMFNTun1BHxqkXfWu06Nu4_bG8XAX8m00yipgLsnk15dDbpPGmuBCEBBT46YbFy_BMbhng7-Fhh8eXCcxZiOjN-yzLX0dNMUoWn7jtL-LtVF6n8KeWxFWXXrFeLdtVlDzL44mq0wj1RAtpGobGPAau-UecDn8i92PwtbTJP0CEeVmb1e924wiZuvP1uG02gDhHW9Q9dMBJzpky65mdxMOy5z53Lm-X0ttiTJV61HQbDWk1OCPKajmF20PjNFH1NJmIVXOtsVNsAZfsP05DFtAcDVHu8FRJevHkM_AwUxYr8Gb-_JJw
