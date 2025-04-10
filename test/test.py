import matplotlib.image as mpimg
import matplotlib.pyplot as plt

from eodag import EODataAccessGateway

dag = EODataAccessGateway()

search_criteria = {
    "provider": "eumetsat_ds",
    "productType": "EO.EUM.DAT.SENTINEL-3.SL_1_RBT___",
    "start": "2024-07-06",
    "end": "2024-07-08",
    "geom": {"lonmin": 14.5, "latmin": 37, "lonmax": 15.5, "latmax": 38},
    "count": True,
}

products_first_page = dag.search(**search_criteria)

fig = plt.figure(figsize=(15, 12))
print(f"Got now {len(products_first_page)} products after filtering by cloud coverage.")
for i, product in enumerate(products_first_page, start=1):
    # This line takes care of downloading the quicklook
    quicklook_path = product.get_quicklook()
    img = mpimg.imread(quicklook_path)
    ax = fig.add_subplot(5, 2, i)
    plt.imshow(img)
plt.tight_layout()
