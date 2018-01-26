# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import os
import sys

from satdl.api.core import SatImagesAPI


def main():
    criteria = {'productType': 'GRD'}
    user_conf = os.path.abspath(os.path.realpath(sys.argv[1]))
    god = SatImagesAPI(user_conf_file_path=user_conf)
    for downloaded_file in god.download_all(god.filter(god.search(criteria['productType']))):
        if downloaded_file is None:
            print('Warning: a file may have been downloaded but we cannot locate it')
        else:
            print('Downloaded {}'.format(downloaded_file))


if __name__ == '__main__':
    main()
