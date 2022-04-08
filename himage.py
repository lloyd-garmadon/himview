#!/usr/bin/python3

##########################################################################################
#
# file:   himage.py
# brief:  High-Bitdepth Image Matrix Wrapper Python Class
# author: Sven Himstedt <sven.himstedt@gmx.de>
#
# LICENSE
#
# HImage was designed to improve personal programming skills. 
# It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY.
#
# HImage is free software:
# You can redistribute it and/or modify it under the terms of the
# GNU General Public License, version 2 as published by the Free Software Foundation
# https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
##########################################################################################

import logging
import copy
import os.path
import re

import numpy as np

from PIL import Image



##########################################################################################
#
# Base class for HImageInfo and HImageStorageInfo
#
##########################################################################################

class _Info():
    PARAM_TYPES = []

    def __init__(self):
        self.params =   { 
                            "None": { 
                                'value': 'None',
                                'values': ['None'],
                                'editable': False
                            }
                        }
        self.validate_params()

    def valid(self):
        return self.ok

    def _validate_params(self, params):
        ok = True
        for param_name in self.PARAM_TYPES:
            if param_name not in params:
                logging.error(f"{self.__class__.__name__} parmeter {param_name} is not present")
                ok = False
            elif isinstance(params[param_name]['values'], list):
                if params[param_name]['value'] not in params[param_name]['values']:
                    logging.error(f"{self.__class__.__name__} with invalid parmeter {param_name}: {params[param_name]['value']} is not in {params[param_name]['values']}")
                    ok = False
            else:
                if (params[param_name]['value'] < 0) or (params[param_name]['value'] > params[param_name]['values']):
                    logging.error(f"{self.__class__.__name__} with invalid parmeter {param_name}: {params[param_name]['value']} is not in range 0..{params[param_name]['values']}")
                    ok = False
        return ok

    def validate_params(self):
        self.ok = self._validate_params(self.params)
        return self.ok

    def freeze_params(self):
        if self.ok:
            for p in self.PARAM_TYPES:
                self.params[p]["editable"] = False

    def dump_params(self):
        logging.error(f"{self.__class__.__name__}")
        logging.error(f"  valid:     {self.ok}")
        for param_name in self.PARAM_TYPES:
            logging.error(f"Parameter: {param_name}")
            logging.error(f"  editable:  {self.params[param_name]['editable']}")
            logging.error(f"  value:     {self.params[param_name]['value']}")
            logging.error(f"  values:    {self.params[param_name]['values']}")

    def get_params(self):
        return self.ok, self.params

    def apply_params(self, params):
        if not self._validate_params(params):
            logging.error(f"{self.__class__.__name__} external parmeter set is not valid")
        else:
            for param_name in self.PARAM_TYPES:
                apply = True
                if not self.params[param_name]['editable']:
                    logging.info(f"{self.__class__.__name__} parmeter {param_name} set is ediable - value not applied")
                    apply = False
                else:
                    if isinstance(self.params[param_name]['values'], list):
                        if params[param_name]['value'] not in self.params[param_name]['values']:
                            # external value is not in valid member value list 
                            logging.info(f"{self.__class__.__name__} parmeter {param_name}: {params[param_name]['value']} is not in {self.params[param_name]['values']} - value not applied")
                            apply = False
                    else:
                        if (params[param_name]['value'] < 0) or (params[param_name]['value'] > self.params[param_name]['values']):
                            logging.info(f"{self.__class__.__name__} parmeter {param_name}: {params[param_name]['value']} is not in range 0..{self.params[param_name]['values']} - value not applied")
                            apply = False
                if apply:
                    self.params[param_name]['value'] = params[param_name]['value']

    def set_value(self, param, value):
        if param not in self.PARAM_TYPES:
            return False
        elif not self.params[param]["editable"]:
            return False
        elif isinstance(self.params[param]['values'], list) and value not in self.params[param]["values"]:
            return False
        elif not isinstance(self.params[param]['values'], list) and ((value < 0) or (value > self.params[param]["values"])):
            return False
        else:
            self.params[param]["value"] = value
            return True

    def get_value(self, param):
        if param not in self.PARAM_TYPES:
            return None
        else: 
            return self.params[param]["value"]

    def set_values(self, param, values):
        if param not in self.PARAM_TYPES:
            return False
        else:
            self.params[param]["values"] = values
            return True

    def get_values(self, param):
        if param not in self.PARAM_TYPES:
            return None
        elif not self.params[param]["editable"]:
            return [ self.params[param]["value"] ]
        else:
            return self.params[param]["values"]

    def set_editable(self, param, editable):
        if param not in self.PARAM_TYPES:
            return False
        else:
            self.params[param]["editable"] = editable
            return True

    def get_editable(self, param):
        if param not in self.PARAM_TYPES:
            return None
        else:
            return self.params[param]["editable"]



##########################################################################################
#
# HImageInfo class
#
# Basic class to hold image dimension and color information 
#
##########################################################################################

class HImageInfo(_Info):

    COLORMODE_NONE    = 'None'
    COLORMODE_MONO    = 'Y'
    COLORMODE_RGB     = 'RGB'
    COLORMODE_YUV444  = 'YUV'
    COLORMODE_YUV422  = 'YUV422'
    COLORMODE_YUV420  = 'YUV420'
    COLORMODE_BAYER_RGGB  = 'rggb'
    COLORMODE_BAYER_GBRG  = 'gbrg'
    COLORMODE_BAYER_BGGR  = 'bggr'
    COLORMODE_BAYER_GRBG  = 'grbg'

    COLORMODES_MONO = [COLORMODE_MONO]
    COLORMODES_BAYER = [COLORMODE_BAYER_RGGB, COLORMODE_BAYER_GBRG, COLORMODE_BAYER_BGGR, COLORMODE_BAYER_GRBG]
    COLORMODES_RGB = [COLORMODE_RGB]
    COLORMODES_YUV = [COLORMODE_YUV444, COLORMODE_YUV422, COLORMODE_YUV420]
    COLORMODES = COLORMODES_MONO + COLORMODES_RGB + COLORMODES_YUV

    PARAM_COLORMODE = "colormode"
    PARAM_BITDEPTH = "bitdepth"
    PARAM_WIDTH = "width"
    PARAM_HEIGHT = "height"
    PARAM_TYPES = [PARAM_BITDEPTH, PARAM_COLORMODE, PARAM_WIDTH, PARAM_HEIGHT]

    def __init__(self, colormode=COLORMODE_NONE, width=0, height=0, bitdepth=0):
        self.ok = True
        self.params = { 
                        self.PARAM_COLORMODE: { 
                            'value': colormode,
                            'values': HImageInfo.COLORMODES,
                            'editable': True
                        },
                        self.PARAM_BITDEPTH: { 
                            'value': bitdepth,
                            'values': [i for i in range(1,32) ],
                            'editable': True
                        },
                        self.PARAM_WIDTH: {
                            'value': width,
                            'values': 16*1024,
                            'editable': True
                        },
                        self.PARAM_HEIGHT: {
                            'value': height,
                            'values': 16*1024,
                            'editable': True
                        }
                    }
        self.validate_params()

    def set_colormode(self, colormode):
        if self.params[self.PARAM_COLORMODE]["editable"]:
            if colormode in self.params[self.PARAM_COLORMODE]["values"]:
                self.params[self.PARAM_COLORMODE]["value"] = colormode
                return self.validate_params()
        return False

    def get_colormode(self):
        if self.ok:
            return self.params[self.PARAM_COLORMODE]["value"]
        else:
            return HImageInfo.COLORMODE_NONE

    def get_components(self):
        if self.ok:
            if ( self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_MONO or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_BAYER_RGGB or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_BAYER_GBRG or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_BAYER_BGGR or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_BAYER_GBRG ) :
                return 1
            if ( self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_RGB or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_YUV444 or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_YUV422 or
                self.params[self.PARAM_COLORMODE]["value"] == HImageInfo.COLORMODE_YUV420 ) :
                return 3
        return 0


    def set_bitdepth(self, bitdepth):
        if self.params[self.PARAM_BITDEPTH]["editable"]:
            if bitdepth in self.params[self.PARAM_BITDEPTH]["values"]:
                self.params[self.PARAM_BITDEPTH]["value"] = bitdepth
                return self.validate_params()
        return False

    def get_bitdepth(self):
        if self.ok:
            return self.params[self.PARAM_BITDEPTH]["value"]
        return 0


    def set_size(self, width, height):
        if self.params[self.PARAM_WIDTH]["editable"] and self.params[self.PARAM_HEIGHT]["editable"]:
            self.params[self.PARAM_WIDTH]["value"] = width
            self.params[self.PARAM_HEIGHT]["value"] = height
            return self.validate_params()
        return False

    def get_size(self):
        if self.ok:
            return self.params[self.PARAM_WIDTH]["value"], self.params[self.PARAM_HEIGHT]["value"]
        return 0,0
        
    def get_width(self):
        if self.ok:
            return self.params[self.PARAM_WIDTH]["value"]
        return 0
        
    def get_height(self):
        if self.ok:
            return self.params[self.PARAM_HEIGHT]["value"]
        return 0
        

    def set_colormode_from_storagemode(self, storagemode):
        if self.params[self.PARAM_COLORMODE]["editable"]:
            if storagemode in HImageStorageInfo.STORAGE_MODES_MONO:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_MONO
                self.params[self.PARAM_COLORMODE]["values"] = HImageInfo.COLORMODES_MONO + HImageInfo.COLORMODES_BAYER
                return True
            if storagemode in HImageStorageInfo.STORAGE_MODES_MIPI:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_MONO
                self.params[self.PARAM_COLORMODE]["values"] = HImageInfo.COLORMODES_MONO + HImageInfo.COLORMODES_BAYER
                return True
            if storagemode in HImageStorageInfo.STORAGE_MODES_RGB:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_RGB
                self.params[self.PARAM_COLORMODE]["values"] = [HImageInfo.COLORMODE_RGB]
                return True
            if storagemode in HImageStorageInfo.STORAGE_MODES_YUV444:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_YUV444
                self.params[self.PARAM_COLORMODE]["values"] = [HImageInfo.COLORMODE_YUV444]
                return True
            if storagemode in HImageStorageInfo.STORAGE_MODES_YUV422:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_YUV422
                self.params[self.PARAM_COLORMODE]["values"] = [HImageInfo.COLORMODE_YUV422]
                return True
            if storagemode in HImageStorageInfo.STORAGE_MODES_YUV420:
                self.params[self.PARAM_COLORMODE]["value"] = HImageInfo.COLORMODE_YUV420
                self.params[self.PARAM_COLORMODE]["values"] = [HImageInfo.COLORMODE_YUV420]
                return True
        return False



##########################################################################################
#
# HImageStorageInfo class
#
# Basic class to describe detailed storage layout information
# of an uncompressed image file
#
##########################################################################################

class HImageStorageInfo(_Info):

    STORAGE_MODE_NONE                    = 'None'
    STORAGE_MODE_MONO                    = 'Monochrome'
    STORAGE_MODE_RGB_RGB_interleaved     = 'RGB interleaved'
    STORAGE_MODE_RGB_BGR_interleaved     = 'BGR interleaved'
    STORAGE_MODE_RGB_RGB_planar          = 'RGB planar'
    STORAGE_MODE_YUV444_YUV_interleaved  = 'YUV interleaved'
    STORAGE_MODE_YUV444_YUV_planar       = 'YUV planar'
    STORAGE_MODE_YUV422_UYVY_interleaved = 'YUV422 UYVY interleaved'
    STORAGE_MODE_YUV422_VYUY_interleaved = 'YUV422 VYUY interleaved'
    STORAGE_MODE_YUV422_YUYV_interleaved = 'YUV422 YUYV interleaved'
    STORAGE_MODE_YUV422_YVYU_interleaved = 'YUV422 YVYU interleaved'
    STORAGE_MODE_YUV422_YUV_planar       = 'YUV422 YUV planar'
    STORAGE_MODE_YUV422_YVU_planar       = 'YUV422 YVU planar'
    STORAGE_MODE_YUV420_YUV_planar       = 'YUV420 YUV planar'
    STORAGE_MODE_YUV420_YVU_planar       = 'YUV420 YVU planar'
    STORAGE_MODE_MIPI_RAW                = 'MIPI RAW'
    STORAGE_MODES_MIPI                   = [ STORAGE_MODE_MIPI_RAW ]
    STORAGE_MODES_MONO                   = [ STORAGE_MODE_MONO ]
    STORAGE_MODES_RGB                    = [ STORAGE_MODE_RGB_RGB_interleaved, STORAGE_MODE_RGB_BGR_interleaved, STORAGE_MODE_RGB_RGB_planar ]
    STORAGE_MODES_YUV444                 = [ STORAGE_MODE_YUV444_YUV_interleaved, STORAGE_MODE_YUV444_YUV_planar ]
    STORAGE_MODES_YUV422                 = [ STORAGE_MODE_YUV422_UYVY_interleaved, STORAGE_MODE_YUV422_VYUY_interleaved, STORAGE_MODE_YUV422_YUYV_interleaved, STORAGE_MODE_YUV422_YVYU_interleaved, STORAGE_MODE_YUV422_YUV_planar, STORAGE_MODE_YUV422_YVU_planar ]
    STORAGE_MODES_YUV420                 = [ STORAGE_MODE_YUV420_YUV_planar, STORAGE_MODE_YUV420_YVU_planar ]
    STORAGE_MODES_PLANAR                 = STORAGE_MODES_MONO + [ STORAGE_MODE_RGB_RGB_planar, STORAGE_MODE_YUV444_YUV_planar, STORAGE_MODE_YUV422_YUV_planar, STORAGE_MODE_YUV422_YVU_planar, STORAGE_MODE_YUV420_YUV_planar, STORAGE_MODE_YUV420_YVU_planar, STORAGE_MODE_MIPI_RAW ]
    STORAGE_MODES_INTERLEAVED            = [ STORAGE_MODE_RGB_RGB_interleaved, STORAGE_MODE_RGB_BGR_interleaved, STORAGE_MODE_YUV444_YUV_interleaved, STORAGE_MODE_YUV422_UYVY_interleaved, STORAGE_MODE_YUV422_VYUY_interleaved, STORAGE_MODE_YUV422_YUYV_interleaved, STORAGE_MODE_YUV422_YVYU_interleaved ]
    STORAGE_MODES                        = STORAGE_MODES_MONO + STORAGE_MODES_MIPI + STORAGE_MODES_RGB + STORAGE_MODES_YUV444 + STORAGE_MODES_YUV422 + STORAGE_MODES_YUV420

    STORAGE_FORMAT_8       = "8 bit"
    STORAGE_FORMAT_16      = "16 bit"
    STORAGE_FORMAT_32      = "32 bit"
    STORAGE_FORMAT_MIPI_10 = "10 bit packed MiPi"
    STORAGE_FORMAT_MIPI_12 = "12 bit packed MiPi"

    STORAGE_FORMATS_RAW  = [ STORAGE_FORMAT_8, STORAGE_FORMAT_16, STORAGE_FORMAT_32 ]
    STORAGE_FORMATS_PACKED = [ STORAGE_FORMAT_MIPI_10, STORAGE_FORMAT_MIPI_12 ]
    STORAGE_FORMATS_MIPI = [ STORAGE_FORMAT_8, STORAGE_FORMAT_MIPI_10, STORAGE_FORMAT_MIPI_12, STORAGE_FORMAT_16 ]
    STORAGE_FORMATS        = STORAGE_FORMATS_RAW + STORAGE_FORMATS_PACKED

    STORAGE_ENDIANESS_LITTLE = 'Little Endian'
    STORAGE_ENDIANESS_BIG    = 'Big Endian'
    STORAGE_ENDIANESS        = [ STORAGE_ENDIANESS_LITTLE, STORAGE_ENDIANESS_BIG ]

    STORAGE_ALIGNMENT_MSB    = 'MSB'
    STORAGE_ALIGNMENT_LSB    = 'LSB'
    STORAGE_ALIGNMENT  = [ STORAGE_ALIGNMENT_MSB , STORAGE_ALIGNMENT_LSB ]

    PARAM_STORAGEMODE = "storagemode"
    PARAM_STORAGEFORMAT = "storageformat"
    PARAM_ENDIANESS = "endianess"
    PARAM_ALIGNMENT = "alignment"
    PARAM_TYPES = [PARAM_STORAGEMODE, PARAM_STORAGEFORMAT, PARAM_ENDIANESS, PARAM_ALIGNMENT]

    def __init__(self):
        self.ok = True
        self.params =  {    self.PARAM_STORAGEMODE: { 
                                'value': HImageStorageInfo.STORAGE_MODE_MONO,
                                'values': HImageStorageInfo.STORAGE_MODES,
                                'editable': True
                            },
                            self.PARAM_STORAGEFORMAT: { 
                                'value': HImageStorageInfo.STORAGE_FORMAT_8,
                                'values': HImageStorageInfo.STORAGE_FORMATS,
                                'editable': True
                            },
                            self.PARAM_ALIGNMENT: { 
                                'value': HImageStorageInfo.STORAGE_ALIGNMENT_MSB,
                                'values': HImageStorageInfo.STORAGE_ALIGNMENT,
                                'editable': True
                            },
                            self.PARAM_ENDIANESS: { 
                                'value': HImageStorageInfo.STORAGE_ENDIANESS_LITTLE,
                                'values': HImageStorageInfo.STORAGE_ENDIANESS,
                                'editable': True
                            }
                        }
        self.validate_params()


    def set_storagemode(self, storagemode):
        if self.params[self.PARAM_STORAGEMODE]["editable"]:
            if storagemode in self.params[self.PARAM_STORAGEMODE]["values"]:
                self.params[self.PARAM_STORAGEMODE]["value"] = storagemode
                return self.validate_params()
        return False

    def get_storagemode(self):
        if self.ok:
            return self.params[self.PARAM_STORAGEMODE]["value"]
        return 0


    def set_storageformat(self, storageformat):
        if self.params[self.PARAM_STORAGEFORMAT]["editable"]:
            if storageformat in self.params[self.PARAM_STORAGEFORMAT]["values"]:
                self.params[self.PARAM_STORAGEFORMAT]["value"] = storageformat
                return self.validate_params()
        return False

    def get_storageformat(self):
        if self.ok:
            return self.params[self.PARAM_STORAGEFORMAT]["value"]
        return 0


    def set_alignment(self, alignment):
        if self.params[self.PARAM_ALIGNMENT]["editable"]:
            if alignment in self.params[self.PARAM_ALIGNMENT]["values"]:
                self.params[self.PARAM_ALIGNMENT]["value"] = alignment
                return self.validate_params()
        return False

    def get_alignment(self):
        if self.ok:
            return self.params[self.PARAM_ALIGNMENT]["value"]
        return 0


    def set_endianess(self, endianess):
        if self.params[self.PARAM_ENDIANESS]["editable"]:
            if endianess in self.params[self.PARAM_ENDIANESS]["values"]:
                self.params[self.PARAM_ENDIANESS]["value"] = endianess
                return self.validate_params()
        return False

    def get_endianess(self):
        if self.ok:
            return self.params[self.PARAM_ENDIANESS]["value"]
        return 0


    def get_bitdepth(self):
        if self.ok:
            storage_format = self.params[self.PARAM_STORAGEFORMAT]["value"]

            if storage_format == HImageStorageInfo.STORAGE_FORMAT_8:
                return 8
            if storage_format == HImageStorageInfo.STORAGE_FORMAT_16:
                return 16
            if storage_format == HImageStorageInfo.STORAGE_FORMAT_32:
                return 32
            if storage_format == HImageStorageInfo.STORAGE_FORMAT_MIPI_10:
                return 10
            if storage_format == HImageStorageInfo.STORAGE_FORMAT_MIPI_12:
                return 12

        return 0


    def get_bpp(self):
        if self.ok:
            bpp = 0

            storage_mode = self.params[self.PARAM_STORAGEMODE]["value"]
            storage_format = self.params[self.PARAM_STORAGEFORMAT]["value"]

            if storage_format == HImageStorageInfo.STORAGE_FORMAT_8:
                bpp = 1
            elif storage_format == HImageStorageInfo.STORAGE_FORMAT_16:
                bpp = 2
            elif storage_format == HImageStorageInfo.STORAGE_FORMAT_32:
                bpp = 4
            elif storage_format == HImageStorageInfo.STORAGE_FORMAT_MIPI_10:
                bpp = 5/4
            elif storage_format == HImageStorageInfo.STORAGE_FORMAT_MIPI_12:
                bpp = 3/2

            if storage_mode in HImageStorageInfo.STORAGE_MODES_MONO :
                return bpp * 1
            elif storage_mode in HImageStorageInfo.STORAGE_MODES_RGB:
                return bpp * 3
            elif storage_mode in HImageStorageInfo.STORAGE_MODES_YUV444:
                return bpp * 3
            elif storage_mode in HImageStorageInfo.STORAGE_MODES_YUV422:
                return bpp * 2
            elif storage_mode in HImageStorageInfo.STORAGE_MODES_YUV420:
                return bpp * 1.5
            elif storage_mode in HImageStorageInfo.STORAGE_MODES_MIPI:
                return bpp

        return 0





##########################################################################################
#
# HImage class
# 
# Fundamental class to hold the image information and image data
#
##########################################################################################

class HImage():

    def __init__(self):

        self.image_info = None
        self.image_pil = None
        self.image_data = []

        self.ok = False


    def valid(self):
        return self.ok

    @classmethod
    def _check_consistency(cls, image_info, image_data):
        if image_info is None:
            logging.error("No imageinfo was given")
            return False
        elif not image_info.validate_params():
            logging.error("imageinfo is not valid")
            return False
        elif image_data is None:
            logging.error("No imagedata was given")
            return False
        elif not isinstance(image_data, list):
            logging.error("imagedata is not correct")
            return False
        elif image_info.get_components() != len(image_data):
            logging.error("image_info and image_data mismatch - number of components")
            return False
        else:
            ok = True
            info_width, info_height = image_info.get_size()
            info_colormode = image_info.get_colormode()
            for comp_index, comp_data in enumerate(image_data, start=0):
                if not isinstance(comp_data, np.ndarray):
                    logging.error("image_data is no valid numpy object")
                    ok = False
                else:
                    data_height, data_width = comp_data.shape
                    if comp_index != 0:
                        if info_colormode == HImageInfo.COLORMODE_YUV422:
                            data_width *= 2
                        elif info_colormode == HImageInfo.COLORMODE_YUV420:
                            data_height *= 2
                            data_width *= 2
                    if info_width != data_width:
                        logging.error("image_info and image_data mismatch - width does not match")
                        ok = False
                    if info_height != data_height:
                        logging.error("image_info and image_data mismatch - height does not match")
                        ok = False
            if ok:
                for i in range(len(image_data)):
                    image_data[i] = image_data[i].astype(np.uint32)

            return ok


    def open(self, file_name=None, storage_info=None, image_info=None, config_function=None):
        if self.ok:
            logging.error("HImage class already initialized")
            return False
        elif not file_name:
            logging.error("no input file given")
            self.ok = False
        elif not os.path.isfile(file_name):
            logging.error("file '{file_name}' does not exist")
            self.ok = False
        else:
            # determine the iamge Reader class and create the image reader
            if (  file_name.lower().endswith(".pgm") or
                file_name.lower().endswith(".ppm") ) :
                himage = HImageReaderPgmPpm(file_name)
            elif (  file_name.lower().endswith(".raw") or
                    file_name.lower().endswith(".rgb") or
                    file_name.lower().endswith(".yuv") or
                    file_name.lower().endswith(".dump") ) :
                himage = HImageReaderRaw(file_name)
            else:
                himage = HImageReaderPIL(file_name)

            # open the image file via image reader class
            storage_info, image_info = himage.open(storage_info, image_info)

            # override the storage and the image info when external configuration function is given
            if config_function is not None:
                self.ok, storage_info, image_info = config_function(storage_info, image_info)

            if self.ok:
                # update the image and storage info when overwritten
                himage.update_storageinfo(storage_info)
                himage.update_imageinfo(image_info)

                # read the image data and close the image file reader        
                himage.read()
                self.ok, self.image_info, self.image_data = himage.close()

        return self.ok


    def create(self, image_info=None, image_data=None):
        if self.ok:
            logging.error("HImage class already initialized")
            return False
        elif not self._check_consistency(image_info, image_data):
            logging.error("HImage class already initialized")
            return False
        else:
            self.image_data = copy.deepcopy(image_data)
            self.image_info = copy.deepcopy(image_info)
            self.ok = self.image_info.validate_params()

            return self.ok


    def get_imageinfo(self):
        if not self.ok: 
            return None
        else:
            return copy.deepcopy(self.image_info)


    def get_imagedata(self, component=-1):
        if not self.ok: 
            return None
        elif component < 0:
            return copy.deepcopy(self.image_data)
        elif self.image_info.get_component() < component:
            return copy.deepcopy(self.image_data[component])


    def get_pixel(self, xpos, ypos, component=-1):
        if not self.ok:
            return None
        elif (xpos < 0) or (xpos >= self.image_info.get_width()):
            return None
        elif (ypos < 0) or (ypos >= self.image_info.get_height()):
            return None
        elif (component >= self.image_info.get_components()):
            return None
        else:
            if self.image_info.get_colormode() == HImageInfo.COLORMODE_YUV422:
                sub = ((1,1),(2,1),(2,1))
            elif self.image_info.get_colormode() == HImageInfo.COLORMODE_YUV420:
                sub = ((1,1),(2,2),(2,2))
            else: 
                sub = ((1,1),(1,1),(1,1))
            color = []
            colors = self.image_info.get_components()
            bitshift = 32 - self.image_info.get_bitdepth()
            for c in range(colors):
                if (component < 0) or (component == c):
                    color.append( self.image_data[c][ypos//sub[c][1]][xpos//sub[c][0]] >> bitshift )
            return color


    def get_image(self):
        if not self.ok: 
            return None
        elif self.image_pil :
            return self.image_pil
        else:
            imagedata = copy.deepcopy(self.image_data)

            image_array_pil = None
            image_mode_pil = None
            if self.image_info.get_colormode() in HImageInfo.COLORMODES_MONO:
                image_mode_pil = 'L'
                image_array_pil = imagedata[0]
            elif self.image_info.get_colormode() in HImageInfo.COLORMODES_BAYER:
                # very implement a simple 'debayering' 
                pixel_array = imagedata[0]
                if self.image_info.get_colormode() in HImageInfo.COLORMODE_BAYER_RGGB:
                    pixel_array_r  = pixel_array[0::2, 0::2]
                    pixel_array_gr = pixel_array[0::2, 1::2]
                    pixel_array_gb = pixel_array[1::2, 0::2]
                    pixel_array_b  = pixel_array[1::2, 1::2]
                    pixel_array_g  = np.hstack((pixel_array_gr,pixel_array_gb))
                if self.image_info.get_colormode() in HImageInfo.COLORMODE_BAYER_BGGR:
                    pixel_array_b  = pixel_array[0::2, 0::2]
                    pixel_array_gb = pixel_array[0::2, 1::2]
                    pixel_array_gr = pixel_array[1::2, 0::2]
                    pixel_array_r  = pixel_array[1::2, 1::2]
                    pixel_array_g  = np.hstack((pixel_array_gb,pixel_array_gr))
                if self.image_info.get_colormode() in HImageInfo.COLORMODE_BAYER_GBRG:
                    pixel_array_gb = pixel_array[0::2, 0::2]
                    pixel_array_b  = pixel_array[0::2, 1::2]
                    pixel_array_r  = pixel_array[1::2, 0::2]
                    pixel_array_gr = pixel_array[1::2, 1::2]
                    pixel_array_g  = np.hstack((pixel_array_gb,pixel_array_gr))
                if self.image_info.get_colormode() in HImageInfo.COLORMODE_BAYER_GRBG:
                    pixel_array_gr = pixel_array[0::2, 0::2]
                    pixel_array_r  = pixel_array[0::2, 1::2]
                    pixel_array_b  = pixel_array[1::2, 0::2]
                    pixel_array_gb = pixel_array[1::2, 1::2]
                    pixel_array_g  = np.hstack((pixel_array_gr,pixel_array_gb))

                pixel_array_g = pixel_array_g.reshape(self.image_info.get_height(), self.image_info.get_width() // 2).repeat(2, axis=1)
                pixel_array_r = pixel_array_r.repeat(2, axis=0).repeat(2, axis=1)
                pixel_array_b = pixel_array_b.repeat(2, axis=0).repeat(2, axis=1)

                image_mode_pil = 'RGB'
                image_array_pil = np.array([pixel_array_r, pixel_array_g, pixel_array_b])
                image_array_pil = image_array_pil.transpose(1,2,0)

            else:
                if self.image_info.get_colormode() == HImageInfo.COLORMODE_RGB:
                    image_mode_pil = 'RGB'
                elif self.image_info.get_colormode() == HImageInfo.COLORMODE_YUV444:
                    image_mode_pil = 'YCbCr'
                elif self.image_info.get_colormode() == HImageInfo.COLORMODE_YUV422:
                    image_mode_pil= 'YCbCr'
                    imagedata[1] = imagedata[1].repeat(2, axis=1)
                    imagedata[2] = imagedata[2].repeat(2, axis=1)
                elif self.image_info.get_colormode() == HImageInfo.COLORMODE_YUV420:
                    image_mode_pil = 'YCbCr'
                    imagedata[1] = imagedata[1].repeat(2, axis=0).repeat(2, axis=1)
                    imagedata[2] = imagedata[2].repeat(2, axis=0).repeat(2, axis=1)

                image_array_pil = np.array([imagedata[0], imagedata[1], imagedata[2]])
                image_array_pil = image_array_pil.transpose(1,2,0)

            if image_mode_pil:
                image_array_pil >>= 24
                image_array_pil = image_array_pil.astype(np.uint8)
                self.image_pil = Image.fromarray(image_array_pil, image_mode_pil)
            else:
                logging.error("failed to create a pil image")

            return self.image_pil





##########################################################################################
#
# HImageReader class
# 
# Basic class to call specific HImageReader classes
#
##########################################################################################

class HImageReader():

    def __init__(self, file_name):
        self.storage_info = None
        self.image_info = None
        self.file_name = None
        self.ok = False
        if not file_name:
            logging.error("no input file given")
        elif not os.path.isfile(file_name):
            logging.error("file '{file_name}' does not exist")
        else:
            self.file_name = file_name

    '''
        Fundametal checks done by the base class
        Shall be called AFTER the implementation of the derived class to return the results
        # e.g.
        # derived class implementation
        # return HImageReader.open(self, ext_storage_info, ext_image_info)
    '''
    def open(self, ext_storage_info, ext_image_info):
        if self.storage_info is None:
            # there is NO internal storage info available - take the external
            self.storage_info = ext_storage_info
        elif ext_storage_info is not None:
            # there is an internal AND an external storage info available
            ext_storage_info_ok, ext_storage_info_params = ext_storage_info.get_params()
            if ext_storage_info_ok:
                self.storage_info.apply_params(ext_storage_info_params)

        if self.image_info is None:
            # there is NO internal iamge info available - take the external
            self.image_info = ext_image_info
        elif ext_image_info is not None:
            # there is an internal AND an external image info available
            ext_image_info_ok, ext_image_info_params = ext_storage_info.get_params()
            if ext_image_info_ok:
                self.image_info.apply_params(ext_image_info_params)

        return self.storage_info, self.image_info


    def update_storageinfo(self, storage_info):
        if storage_info is not None:
            self.storage_info = storage_info
            return self.storage_info.validate_params()
        return False 

    def update_imageinfo(self, image_info):
        if image_info is not None:
            self.image_info = image_info
            return self.image_info.validate_params()
        return False

    '''
        Fundametal checks done by the base class
        Shall be called BEFORE start reading the image data within the derived class
        # e.g.
        # HImageReader.read(self)
        # if self.ok:
        #   derived class implementation ... 
    '''
    def read(self):
        if self.file_name is None:
            self.ok = False
        elif self.storage_info is None:
            self.ok = False
        elif not self.storage_info.valid():
            self.ok = False
        elif self.image_info is None:
            self.ok = False
        elif not self.image_info.valid():
            self.ok = False
        else:
            self.ok = True
    
    '''
        returns the image info and the image data
        Shall be called AFTER close implementation of the derived class to return the results
        # e.g.
        # e.g.
        # derived class implementation
        # return HImageReader.close(self)
    '''
    def close(self):
        if self.ok:
            return self.ok, self.image_info, self.image_data
        else:
            return False, None, None



##########################################################################################
#
# HImageReaderRaw class
# 
# Specific class to read uncompressed raw files
#
##########################################################################################

class HImageReaderRaw(HImageReader):

    def __init__(self, file_name):
        super().__init__(file_name)
        self.image_file = None


    def open(self, ext_storage_info=None, ext_image_info=None):
        if self.file_name is not None:
            # read storage and image info from fileheader (in this case only parsing the filename) 
            match_size            = re.compile('([0-9]+)[xX*]([0-9]+)').findall(self.file_name)
            match_bitdepth        = re.compile('([0-9]+)[bB]').findall(self.file_name)
            match_rgb             = re.compile('[^0-9A-Z]RGB[^0-9A-Z]', re.IGNORECASE).findall(self.file_name)
            match_yuv             = re.compile('[^0-9A-Z]YUV[^0-9A-Z]', re.IGNORECASE).findall(self.file_name)
            match_mipi            = re.compile('[^0-9A-Z]MIPI[^0-9A-Z]', re.IGNORECASE).findall(self.file_name)
            match_subsampling_444 = re.compile('[^0-9]444[^0-9]').findall(self.file_name)
            match_subsampling_422 = re.compile('[^0-9]422[^0-9]').findall(self.file_name)
            match_subsampling_420 = re.compile('[^0-9]420[^0-9]').findall(self.file_name)

            file_ending_rgb = self.file_name.lower().endswith(".rgb")
            file_ending_yuv = self.file_name.lower().endswith(".yuv")
            file_ending_dump = self.file_name.lower().endswith(".dump")

            self.image_info = HImageInfo()
            if len(match_size) == 1:
                self.image_info.set_value(HImageInfo.PARAM_WIDTH, int(match_size[0][0]) )
                self.image_info.set_value(HImageInfo.PARAM_HEIGHT, int(match_size[0][1]))
            if len(match_bitdepth) == 1:
                self.image_info.set_value(HImageInfo.PARAM_BITDEPTH, int(match_bitdepth[0]) )
            if file_ending_dump or len(match_mipi) == 1:
                self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_MONO )
                self.image_info.set_values(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODES_MONO + HImageInfo.COLORMODES_BAYER )
            elif file_ending_rgb or len(match_rgb) == 1:
                self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_RGB )
                self.image_info.set_values(HImageInfo.PARAM_COLORMODE, [ HImageInfo.COLORMODE_RGB ] )
            elif file_ending_yuv or len(match_yuv) == 1:
                if len(match_subsampling_444) == 1:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_YUV444 )
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, [ HImageInfo.COLORMODE_YUV444 ] )
                elif len(match_subsampling_422) == 1:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_YUV422 )
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, [ HImageInfo.COLORMODE_YUV422 ] )
                elif len(match_subsampling_420) == 1:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_YUV420 )
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, [ HImageInfo.COLORMODE_YUV420 ] )
                else:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_YUV444 )
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODES_YUV )
            else:
                self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_MONO )
                self.image_info.set_values(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODES )

            self.storage_info = HImageStorageInfo()
            if file_ending_dump or len(match_mipi) == 1:
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_MIPI_RAW)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_MIPI)
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_MIPI_10)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMATS_MIPI )
                self.storage_info.set_value(HImageStorageInfo.PARAM_ALIGNMENT, HImageStorageInfo.STORAGE_ALIGNMENT_LSB)
            elif file_ending_rgb or len(match_rgb) == 1:
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_RGB_RGB_interleaved)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_RGB)
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_16)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMATS_RAW )
            elif file_ending_yuv or len(match_yuv) == 1:
                if len(match_subsampling_444) == 1:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_YUV444_YUV_interleaved)
                    self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_YUV444)
                elif len(match_subsampling_422) == 1:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_YUV422_UYVY_interleaved)
                    self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_YUV422)
                elif len(match_subsampling_420) == 1:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_YUV420_YUV_planar)
                    self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_YUV420)
                else:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_YUV422_UYVY_interleaved)
                    self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES_YUV444 + HImageStorageInfo.STORAGE_MODES_YUV422 + HImageStorageInfo.STORAGE_MODES_YUV420)
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_16)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMATS_RAW )
            else:
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_MONO)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODES )
                self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_16)
                self.storage_info.set_values(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMATS )

            self.image_file = open(self.file_name, 'rb')

            return HImageReader.open(self, ext_storage_info, ext_image_info)

        return False

    def read(self):
        HImageReader.read(self)

        if self.image_file is None:
            self.ok = False

        if self.ok:
            cursor = self.image_file.tell()
            self.image_file.seek(0, os.SEEK_END)
            filesize = self.image_file.tell() - cursor
            self.image_file.seek(cursor, os.SEEK_SET)

            filesize_expected = self.storage_info.get_bpp()
            filesize_expected *= self.image_info.get_width()
            filesize_expected *= self.image_info.get_height()

            if filesize < filesize_expected:
                logging.error("imagesize too small")
                self.ok = False

        # read the image data
        if self.ok:
            storage_type = "u"
            if self.storage_info.get_storageformat() == HImageStorageInfo.STORAGE_FORMAT_8:
                storage_type = f"{storage_type}1"
            elif self.storage_info.get_storageformat() == HImageStorageInfo.STORAGE_FORMAT_16:
                storage_type = f"{storage_type}2"
            elif self.storage_info.get_storageformat() == HImageStorageInfo.STORAGE_FORMAT_32:
                storage_type = f"{storage_type}4"
            elif self.storage_info.get_storageformat() in HImageStorageInfo.STORAGE_FORMATS_PACKED:
                storage_type = f"{storage_type}1"

            if self.storage_info.get_endianess() == HImageStorageInfo.STORAGE_ENDIANESS_LITTLE:
                storage_type = f"<{storage_type}"
            elif self.storage_info.get_endianess() == HImageStorageInfo.STORAGE_ENDIANESS_BIG:
                storage_type = f">{storage_type}"

            try:
                imagebuffer = np.fromfile(self.image_file, dtype=np.dtype(storage_type), count=filesize)
                imagebuffer = imagebuffer.astype(np.uint32)

                # some special code to depack data
                if self.storage_info.get_storageformat() == HImageStorageInfo.STORAGE_FORMAT_MIPI_10:
                    imagebuffer = np.reshape(imagebuffer, ( -1, 5 ))
                    lsb = imagebuffer[:,4]
                    p_0 = (imagebuffer[:,0] << 2) | ((lsb >> 0 ) & 0x03)
                    p_1 = (imagebuffer[:,1] << 2) | ((lsb >> 2 ) & 0x03)
                    p_2 = (imagebuffer[:,2] << 2) | ((lsb >> 4 ) & 0x03)
                    p_3 = (imagebuffer[:,3] << 2) | ((lsb >> 6 ) & 0x03)
                    imagebuffer = np.transpose(np.vstack((p_0, p_1, p_2, p_3))).reshape(-1)
                    imagebuffer = np.resize(imagebuffer,(self.image_info.get_width() * self.image_info.get_height()))

                elif self.storage_info.get_storageformat() == HImageStorageInfo.STORAGE_FORMAT_MIPI_12:
                    imagebuffer = np.reshape(imagebuffer, ( -1, 3 ))
                    lsb = imagebuffer[:,2]
                    p_0 = (imagebuffer[:,0] << 4) | ((lsb >> 0 ) & 0x0f)
                    p_1 = (imagebuffer[:,1] << 4) | ((lsb >> 4 ) & 0x0f)
                    imagebuffer = np.transpose(np.vstack((p_0, p_1))).reshape(-1)
                    imagebuffer = np.resize(imagebuffer,(self.image_info.get_width() * self.image_info.get_height()))

                if self.storage_info.get_alignment() == HImageStorageInfo.STORAGE_ALIGNMENT_LSB:
                    imagebuffer <<= (32 - self.image_info.get_bitdepth())
                else:
                    imagebuffer <<= (32 - self.storage_info.get_bitdepth())
                    bitmask = ((1 << self.image_info.get_bitdepth()) - 1) << (32 - self.image_info.get_bitdepth())
                    imagebuffer = np.bitwise_and(imagebuffer, bitmask)

            except:
                logging.error(f"loading file failed")
                self.ok = False

        # interprete the image data
        if self.ok:
            image_data = []
            if self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_MONO:
                image_data.append(imagebuffer)

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_MIPI:
                image_data.append(imagebuffer)

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_RGB + HImageStorageInfo.STORAGE_MODES_YUV444:
                if self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_PLANAR:
                    image_array = np.reshape(imagebuffer, ( 3, self.image_info.get_width() * self.image_info.get_height()))

                elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_INTERLEAVED:
                    image_array = np.reshape(imagebuffer, ( self.image_info.get_width() * self.image_info.get_height(), 3)).transpose(1,0)

                if self.storage_info.get_storagemode() == HImageStorageInfo.STORAGE_MODE_RGB_BGR_interleaved:
                    image_data.append(image_array[2,:])
                    image_data.append(image_array[1,:])
                    image_data.append(image_array[0,:])

                else:
                    image_data.append(image_array[0,:])
                    image_data.append(image_array[1,:])
                    image_data.append(image_array[2,:])

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_YUV422:
                if self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_PLANAR:
                    image_array = np.reshape(imagebuffer, ( 2, self.image_info.get_width() * self.image_info.get_height()))

                    luma_array = image_array[0,:]
                    chroma_array = np.reshape(image_array[1,:], ( 2, int(self.image_info.get_width() * self.image_info.get_height() / 2)))

                    image_data.append(luma_array)
                    if self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_YUV_planar ]:
                        image_data.append(chroma_array[0,:])
                        image_data.append(chroma_array[1,:])

                    elif self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_YVU_planar ]:
                        image_data.append(chroma_array[1,:])
                        image_data.append(chroma_array[0,:])

                elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_INTERLEAVED:
                    image_array = np.reshape(imagebuffer, ( self.image_info.get_width() * self.image_info.get_height(), 2)).transpose(1,0)

                    if self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_UYVY_interleaved, HImageStorageInfo.STORAGE_YUV422_VYUY_interleaved ]:
                        luma_array = image_array[1,:]
                        chroma_array = np.reshape(image_array[0,:], ( int(self.image_info.get_width() * self.image_info.get_height() / 2), 2)).transpose(1,0)

                    elif self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_YUYV_interleaved, HImageStorageInfo.STORAGE_YUV422_YVYU_interleaved ]:
                        luma_array = image_array[0,:]
                        chroma_array = np.reshape(image_array[1,:], ( int(self.image_info.get_width() * self.image_info.get_height() / 2), 2)).transpose(1,0)

                    image_data.append(luma_array)
                    if self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_UYVY_interleaved, HImageStorageInfo.STORAGE_YUV422_YUYV_interleaved ]:
                        image_data.append(chroma_array[0,:])
                        image_data.append(chroma_array[1,:])

                    elif self.storage_info.get_storagemode() in [ HImageStorageInfo.STORAGE_YUV422_VYUY_interleaved, HImageStorageInfo.STORAGE_YUV422_YVYU_interleaved ]:
                        image_data.append(chroma_array[1,:])
                        image_data.append(chroma_array[0,:])
            
            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_YUV420:
                logging.error("yuv420 no implemented yet")
                self.ok = False

        if self.ok:
            if self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_MONO:
                image_data[0] = np.reshape(image_data[0], ( self.image_info.get_height(), self.image_info.get_width() ))

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_MIPI:
                image_data[0] = np.reshape(image_data[0], ( self.image_info.get_height(), self.image_info.get_width() ))

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_RGB + HImageStorageInfo.STORAGE_MODES_YUV444:
                image_data[0] = np.reshape(image_data[0], ( self.image_info.get_height(), self.image_info.get_width() ))
                image_data[1] = np.reshape(image_data[1], ( self.image_info.get_height(), self.image_info.get_width() ))
                image_data[2] = np.reshape(image_data[2], ( self.image_info.get_height(), self.image_info.get_width() ))

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_YUV422:
                image_data[0] = np.reshape(image_data[0], ( int(self.image_info.get_height()    ), self.image_info.get_width()))
                image_data[1] = np.reshape(image_data[1], ( int(self.image_info.get_height() / 2), self.image_info.get_width()))
                image_data[2] = np.reshape(image_data[2], ( int(self.image_info.get_height() / 2), self.image_info.get_width()))

            elif self.storage_info.get_storagemode() in HImageStorageInfo.STORAGE_MODES_YUV420:
                image_data[0] = np.reshape(image_data[0], ( int(self.image_info.get_height()    ), int(self.image_info.get_width())))
                image_data[1] = np.reshape(image_data[1], ( int(self.image_info.get_height() / 2), int(self.image_info.get_width() / 2) ))
                image_data[2] = np.reshape(image_data[2], ( int(self.image_info.get_height() / 2), int(self.image_info.get_width() / 2) ))

            self.image_data = image_data

        return self.ok


    def close(self):
        if self.image_file is not None:
            self.image_file.close()

        return HImageReader.close(self)



##########################################################################################
#
# HImageReaderPgmPpm class
# 
# Specific class to read uncompressed pgm and ppm files
#
##########################################################################################

class HImageReaderPgmPpm(HImageReaderRaw):

    def __init__(self, file_name):
        super().__init__(file_name)


    def open(self, ext_storage_info=None, ext_image_info=None):
        if self.file_name is not None:
            self.image_file = open(self.file_name, 'rb')

            # read the magic code
            header = self.image_file.readline()
            header_magic = header[:2]
            # read the next line, and skip comments
            header = self.image_file.readline()
            while header.startswith( b'#' ) :
                header = self.image_file.readline()
            # read the image size
            (header_width, header_height) = [int(i) for i in header.split()]
            header = self.image_file.readline()
            header_maxpix = int(header)

            ok = True
            if header_magic == b'P6':
                # ppm file
                header_colors = 3
            elif header_magic == b'P5':
                # pgm file
                header_colors = 1
            elif header_magic == b'P2':
                logging.error("pgm format P3 is not supported")
                ok = False
            elif header_magic == b'P4':
                logging.error("pgm format P3 is not supported")
                ok = False
            else:
                logging.error(f"File '{self.file_name}' is no valid pgm file")
                ok = False

            # determine the storageinto
            self.storage_info = HImageStorageInfo()
            if ok:
                # determine the storage mode and storage bitdepth

                if header_colors == 3:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_RGB_RGB_interleaved)
                else:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEMODE, HImageStorageInfo.STORAGE_MODE_MONO)
                self.storage_info.set_editable(HImageStorageInfo.PARAM_STORAGEMODE, False)

                if header_maxpix > 255:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_16)
                else:
                    self.storage_info.set_value(HImageStorageInfo.PARAM_STORAGEFORMAT, HImageStorageInfo.STORAGE_FORMAT_8)
                self.storage_info.set_editable(HImageStorageInfo.PARAM_STORAGEFORMAT, False)

                self.storage_info.set_value(HImageStorageInfo.PARAM_ALIGNMENT, HImageStorageInfo.STORAGE_ALIGNMENT_LSB)
                self.storage_info.set_editable(HImageStorageInfo.PARAM_ALIGNMENT, True)

                self.storage_info.set_value(HImageStorageInfo.PARAM_ENDIANESS, HImageStorageInfo.STORAGE_ENDIANESS_BIG)
                self.storage_info.set_editable(HImageStorageInfo.PARAM_ENDIANESS, True)

                ok = self.storage_info.validate_params()

            # determine the imageinfo
            self.image_info = HImageInfo()
            if ok:
                # derive the colormode from the storagemode
                if header_colors == 3:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_RGB)
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, [ HImageInfo.COLORMODE_RGB ] )
                    self.image_info.set_editable(HImageInfo.PARAM_COLORMODE, False)
                else:
                    self.image_info.set_value(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODE_MONO)
                    self.image_info.set_values(HImageInfo.PARAM_COLORMODE, HImageInfo.COLORMODES_MONO + HImageInfo.COLORMODES_BAYER)
                    self.image_info.set_editable(HImageInfo.PARAM_COLORMODE, False)

                # read the image size
                self.image_info.set_value(HImageInfo.PARAM_WIDTH, header_width)
                self.image_info.set_value(HImageInfo.PARAM_HEIGHT, header_height)
                self.image_info.set_values(HImageInfo.PARAM_WIDTH, header_width )
                self.image_info.set_values(HImageInfo.PARAM_HEIGHT, header_height )
                self.image_info.set_editable(HImageInfo.PARAM_WIDTH, False)
                self.image_info.set_editable(HImageInfo.PARAM_HEIGHT, False)

                # read the max value and determine image bitdepth
                image_bitdepth = 0
                for i in range(32):
                    if (1 << i) > header_maxpix:
                        break
                    image_bitdepth += 1
                self.image_info.set_value(HImageInfo.PARAM_BITDEPTH, image_bitdepth)
                self.image_info.set_values(HImageInfo.PARAM_BITDEPTH, [i for i in range (1,self.storage_info.get_bitdepth()+1)])
                self.image_info.set_editable(HImageInfo.PARAM_BITDEPTH, True)

                ok = self.image_info.validate_params()

            if ok:
                return HImageReader.open(self, ext_storage_info, ext_image_info)

        return False



##########################################################################################
#
# HImageReaderPIL class
# 
# Specific class to open non raw file formats via PIL library
# This reader is used as fallback
#
##########################################################################################

class HImageReaderPIL(HImageReader):
    def __init__(self, file_name):
        super().__init__(file_name)
        self.image_pil = None


    def open(self, ext_storage_info=None, ext_image_info=None):
        if self.file_name is not None:
            try:
                self.image_pil = Image.open(self.file_name)

                self.image_info = HImageInfo()
                self.image_info.set_colormode(HImageInfo.COLORMODE_RGB)
                self.image_info.set_bitdepth(8)
                self.image_info.set_size(self.image_pil.size[0], self.image_pil.size[1])
                self.image_info.freeze_params()
            except:
                logging.error(f"opening file '{self.file_name}' failed")
                return False

            self.storage_info = HImageStorageInfo()
            self.storage_info.set_storagemode(HImageStorageInfo.STORAGE_MODE_RGB_RGB_interleaved)
            self.storage_info.set_storageformat(HImageStorageInfo.STORAGE_FORMAT_8)
            self.storage_info.set_alignment(HImageStorageInfo.STORAGE_ALIGNMENT_LSB)
            self.storage_info.set_endianess(HImageStorageInfo.STORAGE_ENDIANESS_LITTLE)
            self.storage_info.freeze_params()

            return HImageReader.open(self, ext_storage_info, ext_image_info)

        return False


    def read(self):
        HImageReader.read(self)

        if self.image_pil is None:
            self.ok = False

        if self.ok:
            image_buffer = np.array(self.image_pil)
            image_buffer = np.reshape(image_buffer, ( self.image_info.get_width() * self.image_info.get_height(), 3))
            image_buffer = image_buffer.transpose(1,0)
            image_buffer = image_buffer.astype(np.uint32)
            image_buffer <<= (32 - self.image_info.get_bitdepth())

            image_data = []
            image_data.append(image_buffer[0,:])
            image_data.append(image_buffer[1,:])
            image_data.append(image_buffer[2,:])
            image_data[0] = np.reshape(image_data[0], ( self.image_info.get_height(), self.image_info.get_width()))
            image_data[1] = np.reshape(image_data[1], ( self.image_info.get_height(), self.image_info.get_width()))
            image_data[2] = np.reshape(image_data[2], ( self.image_info.get_height(), self.image_info.get_width()))

            self.image_data = image_data
        
        return self.ok





##########################################################################################
#
# _HImageOperator class
# 
# Base class for image operations
#
##########################################################################################

class _HImageOperator:
    NAME =          "Dummy Operation"
    DESCRIPTION =   [ 
                        "Performs no operation on the input image\n"
                        "Just returns the given keyword arguments\n" 
                    ]

    INPUT_IMG_COUNT =  1

    ARGUMENTS =     [
                        ["dummy_a", ["a", "b"], "Just a dummy argument is accepted" ],
                        ["dummy_B", ["A", "B"], "Just a dummy argument is accepted"]
                    ]

    _ARG_NAME = 0
    _ARG_VALS = 1
    _ARG_DESCR = 2

    @classmethod
    def get_name(cls):
        return cls.NAME

    @classmethod
    def get_description(cls):
        return cls.DESCRIPTION

    @classmethod
    def get_input_count(cls):
        return cls.INPUT_IMG_COUNT

    @classmethod
    def _init_execute(cls, input_images):
        ok = True
        output_image = None
        output_text = f"Operation {cls.NAME}\n\n"

        if not input_images:
            output_text += "No input images given\n"
            ok = False
        elif len(input_images) != cls.INPUT_IMG_COUNT:
            output_text += "Invalid number of input images\n"
            ok = False

        return ok, output_image, output_text

    @classmethod
    def execute(cls, input_images, **kwargs):
        ok, output_image, output_text = cls._init_execute(input_images)

        if ok:
            output_text += "Keyword arguments allowed:\n"
            for args in cls.DESCRIPTION:
                output_text += f"{args[cls._ARG_NAME]}: {args[cls._ARG_DESCR]} \n"
                for val in args[cls._ARG_VALS]:
                    output_text += f"  {val}\n"

            output_text += "Keyword arguments given:\n"
            for key, value in kwargs.items():
                output_text += f"{key}: {value}\n"

        return ok, output_image, output_text



##########################################################################################
#
# _HImageOperatorDiff class
# 
# Base class for image diff operations
#
##########################################################################################

class _HImageOperatorDiff(_HImageOperator):
    INPUT_IMG_COUNT = 2

    _DIFFMODE_ABS_COLOR = 1
    _DIFFMODE_ABS_ALL   = 2
    _DIFFMODE_REL_COLOR = 3
    _DIFFMODE_REL_ALL   = 4

    _DIFFMODES = [_DIFFMODE_ABS_COLOR, _DIFFMODE_ABS_ALL, _DIFFMODE_REL_COLOR, _DIFFMODE_REL_ALL]

    @classmethod
    def _init_execute(cls, input_images):
        ok, output_image, output_text = super()._init_execute(input_images)

        if ok:
            if not input_images[0].valid():
                output_text += "input Image 0 not valid\n"
                ok = False
            elif not input_images[1].valid():
                output_text += "input Image 1 not valid\n"
                ok = False
            elif input_images[0].image_info.get_width() != input_images[1].image_info.get_width():
                output_text += "Image width does not match\n"
                ok = False
            elif input_images[0].image_info.get_height() != input_images[1].image_info.get_height():
                output_text += "Image height does not match\n"
                ok = False
            elif input_images[0].image_info.get_components() != input_images[1].image_info.get_components():
                output_text += "Color components does not match\n"
                ok = False
            elif input_images[0].image_info.get_components() != 1 and input_images[0].image_info.get_colormode() != input_images[1].image_info.get_colormode():
                output_text += "Colormode does not match\n"
                ok = False
            elif input_images[0].image_info.get_components() <= 1 or input_images[0].image_info.get_components() > 3:
                output_text += "Wrong number of color components\n"
                ok = False

        return ok, output_image, output_text

    @classmethod
    def execute(cls, input_images, **kwargs):
        ok, output_image, output_text = cls._init_execute(input_images)

        if ok:
            if "diffmode" not in kwargs:
                output_text += "No diffmode given\n"
                ok = False
            elif kwargs["diffmode"] not in cls._DIFFMODES:
                output_text += "Unknown diffmode\n"
                ok = False

        if ok:
            diff_mode = kwargs["diffmode"]
            diff_comp = input_images[0].image_info.get_components()

            image_data_A = input_images[0].get_imagedata()
            image_data_B = input_images[1].get_imagedata()
            res_image_data = []

            res_image_bitdepth = max( input_images[0].image_info.get_bitdepth(), input_images[0].image_info.get_bitdepth() )
            res_image_width = input_images[0].image_info.get_width()
            res_image_height = input_images[0].image_info.get_height()
            res_image_colormode = input_images[0].image_info.get_colormode()
            if diff_mode == _HImageOperatorDiff._DIFFMODE_ABS_ALL or diff_mode == _HImageOperatorDiff._DIFFMODE_REL_ALL:
                res_image_colormode = HImageInfo.COLORMODE_MONO
            res_image_info = HImageInfo(colormode=res_image_colormode, width=res_image_width, height=res_image_height, bitdepth=res_image_bitdepth)


            if (diff_mode == _HImageOperatorDiff._DIFFMODE_ABS_COLOR) or (diff_mode == _HImageOperatorDiff._DIFFMODE_ABS_ALL):
                for i in range(diff_comp):
                    image_diff = np.subtract(image_data_A[i], image_data_B[i])
                    np.absolute(image_diff, out=image_diff)
                    res_image_data.append( image_diff )
                if diff_mode == _HImageOperatorDiff._DIFFMODE_ABS_ALL:
                    for i in range(1, diff_comp):
                        res_image_data[0] = np.maximum(res_image_data[0], res_image_data[i])
                    for i in range(1, diff_comp):
                        res_image_data.pop(-1)

            if (diff_mode == _HImageOperatorDiff._DIFFMODE_REL_COLOR) or (diff_mode == _HImageOperatorDiff._DIFFMODE_REL_ALL):
                image_max = 0
                for i in range(diff_comp):
                    image_diff = np.subtract(image_data_A[i], image_data_B[i], dtype=np.double)
                    np.true_divide(image_diff, 2**(32 - res_image_bitdepth),  out=image_diff)
                    image_max = max(image_max,  np.amax(image_diff))
                    image_max = max(image_max, -np.amin(image_diff))
                    res_image_data.append( image_diff )
                image_factor = 1
                if image_max != 0:
                    image_factor = 2**7 / image_max

                for i in range(0, diff_comp):
                    np.multiply(res_image_data[i], image_factor, out=res_image_data[i])
                    np.add(res_image_data[i], 2**7, out=res_image_data[i])
                    np.multiply(res_image_data[i], 2**24, out=res_image_data[i])
                    res_image_data[i] = res_image_data[i].astype(np.uint32)

                if diff_mode == _HImageOperatorDiff._DIFFMODE_REL_ALL:
                    for i in range(1, diff_comp):
                        res_image_data.pop(-1)

        if ok:
            output_image = HImage()
            output_image.create(image_info=res_image_info, image_data=res_image_data)

        return ok, output_image, output_text



##########################################################################################
#
# HImageOperatorDiffXXX classes
# 
# Specific classes for image diff operations
#
##########################################################################################

class HImageOperatorDiffAbsCol(_HImageOperatorDiff):
    NAME = "Absolute Image Difference on each Color Component"
    DESCRIPTION = ( "The absolute difference for each color component between\n"
                    "two images is calculated and a result image is generated\n"
                    "Smaller differences resulting in small color values\n"
                    "Attention:\n"
                    "For images with more than 8 bit accuracty further LSBs\n"
                    "ignored for the result image\n" )
    @classmethod
    def execute(cls, images, **kwargs):
        return super().execute(images, diffmode=cls._DIFFMODE_ABS_COLOR, **kwargs)
class HImageOperatorDiffAbsAll(_HImageOperatorDiff):
    NAME = "Absolute Image Difference over all Color Components"
    DESCRIPTION = ( "The absolute difference for each color component between\n"
                    "two images is calculated. The maximal difference values over\n"
                    "all color components generates a gray result image\n"
                    "Smaller differences resulting in small gray values\n"
                    "Attention:\n"
                    "For images with more than 8 bit accuracty further LSBs\n"
                    "ignored for the result image\n" )
    @classmethod
    def execute(cls, images, **kwargs):
        return super().execute(images, diffmode=cls._DIFFMODE_ABS_ALL, **kwargs)
class HImageOperatorDiffRelCol(_HImageOperatorDiff):
    NAME = "Relative Image Difference on each Color Component"
    DESCRIPTION = ( "The difference for each color component between two images\n"
                    "is calculated. The reslulting values are scaled according\n"
                    "to the maximal aberration and a 8bit colored result image\n"
                    "is generated. Positive differences are resulting\n"
                    "in brighter color values, negative image values in darker\n"
                    "values. Identical values are scalted to the value 128.\n" )
    @classmethod
    def execute(cls, images, **kwargs):
        return super().execute(images, diffmode=cls._DIFFMODE_REL_COLOR, **kwargs)
class HImageOperatorDiffRelAll(_HImageOperatorDiff):
    NAME = "Relative Image Difference over all Color Components"
    DESCRIPTION = ( "The difference for each color component between two\n"
                    "images is calculated. The maximal difference values\n"
                    "over all color components generates 8bit gray result image\n"
                    "The reslulting values are scaled according to the maximal\n"
                    "aberration. Positive differences are resulting\n"
                    "in brighter color values, negative image values in darker\n"
                    "values. Identical values are scalted to the gray value 128.\n" )
    @classmethod
    def execute(cls, images, **kwargs):
        return super().execute(images, diffmode=cls._DIFFMODE_REL_ALL, **kwargs)



