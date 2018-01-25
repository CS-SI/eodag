# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from satdl.api.core import SatImagesAPI


def main():
    criteria = {'productType': 'L1C'}
    god = SatImagesAPI()
    for downloaded_file in god.download_all(god.filter(god.search(criteria['productType']))):
        if downloaded_file is None:
            print('Warning: a file may have been downloaded but we cannot locate it')
        else:
            print('Downloaded {}'.format(downloaded_file))


if __name__ == '__main__':
    main()
