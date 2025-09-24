import cartopy.crs as ccrs
import cartopy.feature as cfeature
import h5py
import matplotlib.pyplot as plt
import numpy as np

# Ouvre le fichier H5
filename = "/home/tlarrouy/eodag/download/2c54135a-3e34-4b90-bdf5-3754bf840063/data/ACCLIP/AerosolCloud_AircraftRemoteSensing_WB57_Data_1/acclip-Roscoe-L1B-up_WB57_20220714_R0.h5"
with h5py.File(filename, "r") as f:
    lats = f["Latitude"][:]
    lons = f["Longitude"][:]
    atb = f["ATB_1064"][:]  # shape (NumRecs, NumBins)
    bin_alt = f["Bin_Alt"][:]

# Moyenne verticale pour avoir une seule valeur par enregistrement
atb_mean = np.mean(atb, axis=1)  # shape (NumRecs,)

# Affichage sur carte
plt.figure(figsize=(12, 6))
ax = plt.axes(projection=ccrs.PlateCarree())
sc = ax.scatter(
    lons, lats, c=atb_mean, cmap="viridis", s=10, transform=ccrs.PlateCarree()
)
ax.add_feature(cfeature.COASTLINE)
ax.add_feature(cfeature.BORDERS)
ax.set_title("ACCLIP ATB_1064 mean intensity")
plt.colorbar(sc, label="ATB_1064 intensity")
plt.show()
