from eodag import EODataAccessGateway, setup_logging

setup_logging(3)

dag = EODataAccessGateway()

search_criteria = {
    "provider": "dedl",
    "productType": "S3_SLSTR_L1RBT",
    "start": "2024-07-06",
    "end": "2024-07-08",
    "geom": {"lonmin": 14.5, "latmin": 37, "lonmax": 15.5, "latmax": 38},
    "count": True,
}

products_first_page = dag.search(**search_criteria)

quicklook_path = products_first_page[0].get_quicklook()

print(quicklook_path)
