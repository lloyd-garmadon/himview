#!/usr/bin/python3

##########################################################################################
#
# file:   himview.py
# brief:  High-Bitdepth Image Matrix Viewer Python Class
# author: Sven Himstedt <sven.himstedt@gmx.de>
#
# LICENSE
#
# HimView was designed to improve personal programming skills. 
# It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY.
#
# HimView is free software:
# You can redistribute it and/or modify it under the terms of the
# GNU General Public License, version 2 as published by the Free Software Foundation
# https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
##########################################################################################

import sys
import os.path
import logging
import copy
import re
import time
import json
import glob

from himage import HImage, HImageInfo, HImageStorageInfo

import numpy as np

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

from PIL import Image, ImageTk

g_status = None





class ImageNotebook(ttk.Notebook):
    __initialized = False

    def __init__(self, *args, **kwargs):
        if not self.__initialized:
            self.__initialize_custom_style()
            self.__inititialized = True

        kwargs["style"] = "ImageNotebook"
        ttk.Notebook.__init__(self, *args, **kwargs)

        self._active = None

        self.bind("<ButtonPress-1>", self.on_close_press, True)
        self.bind("<ButtonRelease-1>", self.on_close_release)

    def on_close_press(self, event):
        element = self.identify(event.x, event.y)

        if "close" in element:
            index = self.index("@%d,%d" % (event.x, event.y))
            self.state(['pressed'])
            self._active = index

    def on_close_release(self, event):
        if not self.instate(['pressed']):
            return

        element =  self.identify(event.x, event.y)
        index = self.index("@%d,%d" % (event.x, event.y))

        if "close" in element and self._active == index:
            self.forget(index)
            self.event_generate("<<NotebookTabClosed>>")

        self.state(["!pressed"])
        self._active = None

    def __initialize_custom_style(self):
        style = ttk.Style()
        self.images = (
            tk.PhotoImage("img_close", data='''
                R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
                '''),
            tk.PhotoImage("img_closeactive", data='''
                R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH5BAEKAAQALAAA
                AAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU5kEJADs=
                '''),
            tk.PhotoImage("img_closepressed", data='''
                R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
            ''')
        )

        style.element_create("close", "image", "img_close",
                            ("active", "pressed", "!disabled", "img_closepressed"),
                            ("active", "!disabled", "img_closeactive"), border=8, sticky='')
        style.layout("ImageNotebook", [("ImageNotebook.client", {"sticky": "nswe"})])
        style.layout("ImageNotebook.Tab", [
            ("ImageNotebook.tab", {
                "sticky": "nswe", 
                "children": [
                    ("ImageNotebook.padding", {
                        "side": "top", 
                        "sticky": "nswe",
                        "children": [
                            ("ImageNotebook.focus", {
                                "side": "top", 
                                "sticky": "nswe",
                                "children": [
                                    ("ImageNotebook.label", {"side": "left", "sticky": ''}),
                                    ("ImageNotebook.close", {"side": "left", "sticky": ''}),
                                ]
                        })
                    ]
                })
            ]
        })
    ])


class ImageTab(ttk.Frame):

    '''
    ' class variables constructor
    '''

    param_scalestep = 1.3

    current_scale = 1.0
    current_xoffset = 0
    current_yoffset = 0

    scaled_image_xsize = 0
    scaled_image_ysize = 0
    scaled_image_xoffset = 0
    scaled_image_yoffset = 0

    visible_scaled_image_region = (0,0,1,1)
    visible_orig_image_region = (0,0,1,1)

    '''
    ' constructor
    '''

    def __init__(self, master, himage, name):

        ttk.Frame.__init__(self, master)

        self.name = name

        # Create canvas and put image on it
        self.canvas = tk.Canvas(self.master, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nswe')
        self.canvas.update()  # wait till canvas is created

        # Make the canvas expandable
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

        # image values
        self.img = himage
        self.img_xoffset = 0
        self.img_yoffset = 0
        self.img_xsize = himage.image_info.get_width()
        self.img_ysize = himage.image_info.get_height()

        # Bind events to the Canvas
        self.canvas.bind("<Visibility>",        self.__redraw)
        self.canvas.bind('<Configure>',         self.__redraw     )   # canvas is resized
        self.canvas.bind('<Double-Button-1>',   self.__reset      )   # double click left mouse button    
        self.canvas.bind('<ButtonPress-1>',     self.__move_from  )   # press left mouse button
        self.canvas.bind('<B1-Motion>',         self.__move       )   # press left mouse button and move mouse
        self.canvas.bind('<MouseWheel>',        self.__wheel      )   # with Windows and MacOS, but not Linux
        self.canvas.bind('<Button-5>',          self.__wheel      )   # only with Linux, wheel scroll down
        self.canvas.bind('<Button-4>',          self.__wheel      )   # only with Linux, wheel scroll up
        self.canvas.bind('<Motion>',            self.__pointer    )
        self.__redraw()

    '''
    ' internal functions
    '''

    def __pointer(self, event):
        global g_status
        if (    event.x > ImageTab.visible_scaled_image_region[0] and
                event.x < ImageTab.visible_scaled_image_region[2] and
                event.y > ImageTab.visible_scaled_image_region[1] and
                event.y < ImageTab.visible_scaled_image_region[3] ) :
            xpos = int( ImageTab.visible_orig_image_region[0] + (event.x - ImageTab.visible_scaled_image_region[0]) / (ImageTab.visible_scaled_image_region[2] - ImageTab.visible_scaled_image_region[0]) * (ImageTab.visible_orig_image_region[2] - ImageTab.visible_orig_image_region[0]) )
            ypos = int( ImageTab.visible_orig_image_region[1] + (event.y - ImageTab.visible_scaled_image_region[1]) / (ImageTab.visible_scaled_image_region[3] - ImageTab.visible_scaled_image_region[1]) * (ImageTab.visible_orig_image_region[3] - ImageTab.visible_orig_image_region[1]) )
            xsize = self.img.image_info.get_width()
            ysize = self.img.image_info.get_height()
            size_digits = 3
            mode = self.img.image_info.get_colormode()
            bitdepth = self.img.image_info.get_bitdepth()
            bitdepth_digits = 2 + (bitdepth + 3) // 4
            colors = self.img.get_pixel(xpos, ypos)
            if colors:
                g_status.set(   f"Image: [{xsize}x{ysize}] - " + 
                                f"Mode: [{mode} {bitdepth}bit] - " + 
                                f"Position: [" + "{0:#{1}}".format(xpos, size_digits) + "x" + "{0:#{1}}".format(ypos, size_digits) + "] - "
                                f"Color: [" + ", ".join("{0:#0{1}x}".format(num, bitdepth_digits) for num in colors) + "]"
                            )


    def __move_from(self, event):
        self.move_from_x = event.x
        self.move_from_y = event.y

    def __move(self, event):
        delta_xoffset = event.x - self.move_from_x
        delta_yoffset = event.y - self.move_from_y
        self.move_from_x = event.x
        self.move_from_y = event.y
        self.__redraw(event=event, delta_xoffset=delta_xoffset, delta_yoffset=delta_yoffset)

    def __wheel(self, event):
        # Respond to Linux (event.num) or Windows (event.delta) wheel event
        delta_scale = 0
        if event.num == 5 or event.delta == -120:  # scroll down
            delta_scale = ImageTab.current_scale * ImageTab.param_scalestep - ImageTab.current_scale
        if event.num == 4 or event.delta == 120:  # scroll up
            delta_scale = ImageTab.current_scale - ImageTab.current_scale * ImageTab.param_scalestep
        self.__redraw(event=event, delta_scale=delta_scale)

    def __reset(self, event=None):
        ImageTab.current_scale = 1.0
        ImageTab.current_xoffset = 0
        ImageTab.current_yoffset = 0
        self.__redraw()

    def __redraw(self, event=None, delta_scale=None, delta_xoffset=None, delta_yoffset=None):
        print( f"redraw image " )
        print( f"event {event}" )

        # visible canvas region
        canvas_xsize = self.canvas.winfo_width()
        canvas_ysize = self.canvas.winfo_height()
        canvas_region= ( 0, 0, canvas_xsize + 1, canvas_ysize + 1)
        print( f"canvas                     :  {0},{0} {canvas_xsize}x{canvas_ysize} - {canvas_region}" )

        # apply delta values before calculating the image to display on the canvas
        if delta_xoffset:
            ImageTab.current_xoffset += delta_xoffset
        if delta_yoffset:
            ImageTab.current_yoffset += delta_yoffset
        if delta_scale:
            ImageTab.current_scale += delta_scale

        #scaled image size, offsest and region
        scaled_image_xsize = int(self.img_xsize * ImageTab.current_scale )
        scaled_image_ysize = int(self.img_ysize * ImageTab.current_scale )
        scaled_image_xoffset = int((canvas_xsize - scaled_image_xsize) / 2) + ImageTab.current_xoffset
        scaled_image_yoffset = int((canvas_ysize - scaled_image_ysize) / 2) + ImageTab.current_yoffset

        # adjust the scaling center when the mouse pointer is within the visible image size
        if event and delta_scale:
            if (    event.x > ImageTab.visible_scaled_image_region[0] and
                    event.x < ImageTab.visible_scaled_image_region[2] and
                    event.y > ImageTab.visible_scaled_image_region[1] and
                    event.y < ImageTab.visible_scaled_image_region[3] ) :
                offset_adjust_x = int(event.x - scaled_image_xoffset - ((event.x - ImageTab.scaled_image_xoffset) / ImageTab.scaled_image_xsize) * scaled_image_xsize)
                offset_adjust_y = int(event.y - scaled_image_yoffset - ((event.y - ImageTab.scaled_image_yoffset) / ImageTab.scaled_image_ysize) * scaled_image_ysize)
                scaled_image_xoffset += offset_adjust_x
                scaled_image_yoffset += offset_adjust_y
                ImageTab.current_xoffset += offset_adjust_x
                ImageTab.current_yoffset += offset_adjust_y

        ImageTab.scaled_image_xsize = scaled_image_xsize
        ImageTab.scaled_image_ysize = scaled_image_ysize
        ImageTab.scaled_image_xoffset = scaled_image_xoffset
        ImageTab.scaled_image_yoffset = scaled_image_yoffset
        scaled_image_region =  (scaled_image_xoffset, scaled_image_yoffset, scaled_image_xsize + scaled_image_xoffset + 1, scaled_image_ysize + scaled_image_yoffset + 1 )
        ImageTab.scaled_image_region = scaled_image_region
        print( f"scaled_image_region        :  {scaled_image_xoffset},{scaled_image_yoffset} {scaled_image_xsize}x{scaled_image_ysize} - {scaled_image_region}" )

        #visible scaled image area on canvas
        visible_scaled_image_region = ( min( max( canvas_region[0], scaled_image_region[0] ), canvas_region[2] ), 
                                        min( max( canvas_region[1], scaled_image_region[1] ), canvas_region[3] ), 
                                        max( min( canvas_region[2], scaled_image_region[2] ), canvas_region[0] ), 
                                        max( min( canvas_region[3], scaled_image_region[3] ), canvas_region[1] ) )
        visible_scaled_image_xsize = visible_scaled_image_region[2] - visible_scaled_image_region[0] - 1
        visible_scaled_image_ysize = visible_scaled_image_region[3] - visible_scaled_image_region[1] - 1 
        visible_scaled_image_xoffset = visible_scaled_image_region[0]
        visible_scaled_image_yoffset = visible_scaled_image_region[1]
        ImageTab.visible_scaled_image_region = visible_scaled_image_region
        print( f"visible_scaled_image_region:  {visible_scaled_image_xoffset},{visible_scaled_image_yoffset} {visible_scaled_image_xsize}x{visible_scaled_image_ysize} - {visible_scaled_image_region}" )

        # visible original image region
        if visible_scaled_image_xoffset > 0 :
            visible_orig_image_xoffset = 0
        else :
            visible_orig_image_xoffset = int( -scaled_image_xoffset / ImageTab.current_scale )

        if visible_scaled_image_yoffset > 0 :
            visible_orig_image_yoffset = 0
        else :
            visible_orig_image_yoffset = int( -scaled_image_yoffset / ImageTab.current_scale )

        visible_orig_image_xsize = int(visible_scaled_image_xsize / ImageTab.current_scale )
        visible_orig_image_ysize = int(visible_scaled_image_ysize / ImageTab.current_scale )

        visible_orig_image_region = (   visible_orig_image_xoffset, 
                                        visible_orig_image_yoffset, 
                                        visible_orig_image_xoffset + visible_orig_image_xsize + 1, 
                                        visible_orig_image_yoffset + visible_orig_image_ysize + 1)

        ImageTab.visible_orig_image_region = visible_orig_image_region
        print( f"visible_orig_image_region  :  {visible_orig_image_xoffset},{visible_orig_image_yoffset} {visible_orig_image_xsize}x{visible_orig_image_ysize} - {visible_orig_image_region}" )

        if visible_scaled_image_xsize > 0  and visible_scaled_image_ysize > 0:
            image = self.img.get_image()
            image = image.crop( visible_orig_image_region).resize( (visible_scaled_image_xsize, visible_scaled_image_ysize), resample=Image.NEAREST)
            imagetk = ImageTk.PhotoImage(image)
            imageid = self.canvas.create_image( visible_scaled_image_xoffset, visible_scaled_image_yoffset, anchor='nw', image=imagetk)

            self.canvas.imagetk = imagetk  # keep an extra reference to prevent garbage-collection




class Splash(tk.Toplevel):
    def __init__(self, parent, filename):
        self.parent = None
        if not os.path.isabs(filename):
            filename = f"{os.path.dirname(os.path.realpath(__file__))}/{filename}"
        if os.path.isfile(filename):
            self.parent = parent
            self.parent.withdraw()
            tk.Toplevel.__init__(self, parent)
            screen_width = parent.winfo_screenwidth()
            screen_height = parent.winfo_screenheight()
            img = tk.PhotoImage(file=filename)
            window_width = img.width()
            window_height = img.height()
            window_offset_x = (screen_width - window_width) // 2
            window_offset_y = (screen_height - window_height) // 2
            self.geometry(f"{window_width}x{window_height}+{window_offset_x}+{window_offset_y}")
            self.wm_overrideredirect(True) 
            panel = tk.Label(self, image = img)
            panel.pack()
            self.update()

    def display(self, display_time):
        if self.parent:
            time.sleep(display_time)
            self.destroy()
            self.parent.deiconify()            


class HIMView(tk.Tk):

    '''
    ' constructor
    '''

    def __init__(self, nosplash=False):
        tk.Tk.__init__(self)

        global g_status
        g_status = tk.StringVar('')

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 800
        window_height = 600
        window_offset_x = (screen_width - window_width) // 2
        window_offset_y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{window_offset_x}+{window_offset_y}")
        self.title("HIM View")

        if not nosplash:
            Splash(self, "himview_splash.ppm").display(3)

        self.menu = tk.Menu(self)

        self.menu_file = tk.Menu(self.menu, tearoff=0)
        self.menu_file.add_command(label='Open',        command=self.dialog_file_open )
        self.menu_file.add_command(label="Exit",        command=self.quit )
        self.menu.add_cascade(label='File', menu=self.menu_file)

        self.menu_edit = tk.Menu(self.menu, tearoff=0)
        self.menu_edit.add_command(label='Histogram',                       command=self.dialog_not_implemented)
        self.menu_edit.add_command(label='Absolute Difference (colored)',   command=self.dialog_abs_diff_col)
        self.menu_edit.add_command(label='Absolute Difference (grey)',      command=self.dialog_abs_diff_grey)
        self.menu_edit.add_command(label='Scaled Difference (colored)',     command=self.dialog_rel_diff_col)
        self.menu_edit.add_command(label='Scaled Difference (grey)',        command=self.dialog_rel_diff_grey)
        self.menu.add_cascade(label='Edit', menu=self.menu_edit)

        self.config(menu=self.menu)

        self.frame_image_tab = ttk.Frame(self, relief=tk.RAISED, borderwidth=1)
        self.frame_image_tab.pack(fill=tk.BOTH, side=tk.TOP, expand=True, )

        self.tab_control = ImageNotebook(self.frame_image_tab)
        self.tab_control.enable_traversal()
        self.tab_control.pack(expand=1, fill='both')


        self.frame_status_bar = ttk.Frame(self, relief=tk.RAISED, borderwidth=1)
        self.frame_status_bar.pack(fill=tk.X, side=tk.BOTTOM, expand=False)

        self.status_bar = ttk.Label(self.frame_status_bar, text="Here I am ..... ")
        self.status_bar.config(textvariable=g_status)
        self.status_bar.config(font=("Courier", 10))
        self.status_bar.pack(fill=tk.X, expand=True)

        self.update()

    '''
    ' helper functions
    '''

    def open_image_tab(self, tab_image, tab_name):
        if tab_image:
            if tab_image.ok :
                if not tab_name:
                    tab_name = "image"
                tab_frame = ttk.Frame(self.tab_control)
                ImageTab(master=tab_frame, name=tab_name, himage=tab_image)
                self.tab_control.add(tab_frame, text=tab_name)
                self.tab_control.select( tab_frame )


    '''
    ' dialog functions
    '''

    def dialog_configure_image(self, storageinfo, imageinfo):
        ok = False

        d = tk.Toplevel(self)
        d.geometry(f"+{self.winfo_x() + self.winfo_width() // 4}+{self.winfo_y() + self.winfo_height() // 4}")

        fr = ttk.Frame(d)
        fr.master.title("Image Data Configuration")
        fr.style = ttk.Style()
        fr.style.theme_use("default")
        fr.pack(fill=tk.BOTH, expand=True)

        fr_name = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
        fr_name.pack(fill=tk.BOTH, expand=True)

        name = "File Config"

        name_title_frame = ttk.Frame(fr_name)
        name_title_frame.pack(fill=tk.X, anchor=tk.N)
        name_title_lable = ttk.Label(name_title_frame, text=name)
        name_title_lable.pack(side=tk.LEFT, padx=5, pady=5)



        fr_im = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
        fr_im.pack(fill=tk.BOTH, expand=True)

        image_title_frame = ttk.Frame(fr_im)
        image_title_frame.pack(fill=tk.X, anchor=tk.N)
        image_title_lable = ttk.Label(image_title_frame, text="Image Configuration")
        image_title_lable.pack(side=tk.LEFT, padx=5, pady=5)

        param = HImageInfo.PARAM_WIDTH
        image_xsize_var = tk.IntVar()
        image_xsize_frame = ttk.Frame(fr_im)
        image_xsize_frame.pack(fill=tk.X, anchor=tk.N)
        image_xsize_label = ttk.Label(image_xsize_frame, text=param, width=15)
        image_xsize_label.pack(side=tk.LEFT, padx=5, pady=5)
        if imageinfo.get_editable(param) :
            image_xsize_entry = ttk.Entry(image_xsize_frame)
            image_xsize_entry.insert(tk.END, imageinfo.get_value(param))
        else:
            image_xsize_entry = ttk.Label(image_xsize_frame)
        image_xsize_entry.config(textvariable=image_xsize_var)
        image_xsize_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageInfo.PARAM_HEIGHT
        image_ysize_var = tk.IntVar()
        image_ysize_frame = ttk.Frame(fr_im)
        image_ysize_frame.pack(fill=tk.X, anchor=tk.N)
        image_ysize_label = ttk.Label(image_ysize_frame, text=param, width=15)
        image_ysize_label.pack(side=tk.LEFT, padx=5, pady=5)
        if imageinfo.get_editable(param) :
            image_ysize_entry = ttk.Entry(image_ysize_frame)
            image_ysize_entry.insert(tk.END, imageinfo.get_value(param))
        else:
            image_ysize_entry = ttk.Label(image_ysize_frame)
        image_ysize_entry.config(textvariable=image_ysize_var)
        image_ysize_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageInfo.PARAM_BITDEPTH
        image_bitdepth_var = tk.IntVar()
        image_bitdepth_frame = ttk.Frame(fr_im)
        image_bitdepth_frame.pack(fill=tk.X, anchor=tk.N)
        image_bitdepth_label = ttk.Label(image_bitdepth_frame, text=param, width=15)
        image_bitdepth_label.pack(side=tk.LEFT, padx=5, pady=5)
        if imageinfo.get_editable(param) :
            image_bitdepth_entry = ttk.Combobox(image_bitdepth_frame, values = imageinfo.get_values(param), state = 'readonly' )
        else:
            image_bitdepth_entry = ttk.Label(image_bitdepth_frame)
        image_bitdepth_entry.config(textvariable=image_bitdepth_var)
        image_bitdepth_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageInfo.PARAM_COLORMODE
        image_colormode_var = tk.StringVar()
        image_colormode_frame = ttk.Frame(fr_im)
        image_colormode_frame.pack(fill=tk.X, anchor=tk.N)
        image_colormode_label = ttk.Label(image_colormode_frame, text=param, width=15)
        image_colormode_label.pack(side=tk.LEFT, padx=5, pady=5)
        if imageinfo.get_editable(param) :
            image_colormode_entry = ttk.Combobox(image_colormode_frame, values = imageinfo.get_values(param), state = 'readonly' )
        else:
            image_colormode_entry = ttk.Label(image_colormode_frame)
        image_colormode_entry.config(textvariable=image_colormode_var)
        image_colormode_entry.pack(fill=tk.X, padx=5, expand=True)

        def image_value_set():
            param = HImageInfo.PARAM_WIDTH
            image_xsize_var.set( imageinfo.get_value(param) )
            param = HImageInfo.PARAM_HEIGHT
            image_ysize_var.set( imageinfo.get_value(param) )
            param = HImageInfo.PARAM_BITDEPTH
            image_bitdepth_var.set( imageinfo.get_value(param) )
            param = HImageInfo.PARAM_COLORMODE
            image_colormode_var.set( imageinfo.get_value(param) )

        def imageinfo_update():
            imageinfo.set_bitdepth(image_bitdepth_var.get())
            imageinfo.set_size(image_xsize_var.get(), image_ysize_var.get())
            imageinfo.set_colormode(image_colormode_var.get())


        fr_st = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
        fr_st.pack(fill=tk.BOTH, expand=True)

        storage_title_frame = ttk.Frame(fr_st)
        storage_title_frame.pack(fill=tk.X, anchor=tk.N)
        storage_title_label = ttk.Label(storage_title_frame, text="Storage Configuration")
        storage_title_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        param = HImageStorageInfo.PARAM_STORAGEMODE
        storage_mode_var = tk.StringVar('')
        storage_mode_frame = ttk.Frame(fr_st)
        storage_mode_frame.pack(fill=tk.X, anchor=tk.N)
        storage_mode_label = ttk.Label(storage_mode_frame, text=param, width=15)
        storage_mode_label.pack(side=tk.LEFT, padx=5, pady=5)
        if storageinfo.get_editable(param) :
            storage_mode_entry = ttk.Combobox(storage_mode_frame, values = storageinfo.get_values(param), state = 'readonly' )
        else:
            storage_mode_entry = ttk.Label(storage_mode_frame)
        storage_mode_entry.config(textvariable=storage_mode_var)
        storage_mode_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageStorageInfo.PARAM_STORAGEFORMAT
        storage_format_var = tk.StringVar()
        storage_format_frame = ttk.Frame(fr_st)
        storage_format_frame.pack(fill=tk.X, anchor=tk.N)
        storage_format_label = ttk.Label(storage_format_frame, text=param, width=15)
        storage_format_label.pack(side=tk.LEFT, padx=5, pady=5)
        if storageinfo.get_editable(param) :
            storage_format_entry = ttk.Combobox(storage_format_frame, values = storageinfo.get_values(param), state = 'readonly' )
        else:
            storage_format_entry = ttk.Label(storage_format_frame)
        storage_format_entry.config(textvariable=storage_format_var)
        storage_format_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageStorageInfo.PARAM_ALIGNMENT
        storage_alignment_var = tk.StringVar('')
        storage_alignment_frame = ttk.Frame(fr_st)
        storage_alignment_frame.pack(fill=tk.X, anchor=tk.N)
        storage_alignment_label = ttk.Label(storage_alignment_frame, text=param, width=15)
        storage_alignment_label.pack(side=tk.LEFT, padx=5, pady=5)
        if storageinfo.get_editable(param) :
            storage_alignment_entry = ttk.Combobox(storage_alignment_frame,  text = storageinfo.get_value(param), values = storageinfo.get_values(param), state = 'readonly' )
        else:
            storage_alignment_entry = ttk.Label(storage_alignment_frame)
        storage_alignment_entry.config(textvariable=storage_alignment_var)
        storage_alignment_entry.pack(fill=tk.X, padx=5, expand=True)

        param = HImageStorageInfo.PARAM_ENDIANESS
        storage_endianess_var = tk.StringVar('')
        storage_endianess_frame = ttk.Frame(fr_st)
        storage_endianess_frame.pack(fill=tk.X, anchor=tk.N)
        storage_endianess_label = ttk.Label(storage_endianess_frame, text=param, width=15)
        storage_endianess_label.pack(side=tk.LEFT, padx=5, pady=5)
        if storageinfo.get_editable(param) :
            storage_endianess_entry = ttk.Combobox(storage_endianess_frame,  text = storageinfo.get_value(param), values = storageinfo.get_values(param), state = 'readonly' )
        else:
            storage_endianess_entry = ttk.Label(storage_endianess_frame)
        storage_endianess_entry.config(textvariable=storage_endianess_var)
        storage_endianess_entry.pack(fill=tk.X, padx=5, expand=True)

        def storage_value_set():
            param = HImageStorageInfo.PARAM_STORAGEMODE
            storage_mode_var.set( storageinfo.get_value(param) )
            param = HImageStorageInfo.PARAM_STORAGEFORMAT
            storage_format_var.set( storageinfo.get_value(param) )
            param = HImageStorageInfo.PARAM_ALIGNMENT
            storage_alignment_var.set( storageinfo.get_value(param) )
            param = HImageStorageInfo.PARAM_ENDIANESS
            storage_endianess_var.set( storageinfo.get_value(param) )

        def storageinfo_update():
            # update the imageinfo and storage info references
            storageinfo.set_storagemode(storage_mode_var.get())
            storageinfo.set_storageformat(storage_format_var.get())
            storageinfo.set_alignment(storage_alignment_var.get())
            storageinfo.set_endianess(storage_endianess_var.get())


        fr_pre = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
        fr_pre.pack(fill=tk.BOTH, expand=True)

        preset_title_frame = ttk.Frame(fr_pre)
        preset_title_frame.pack(fill=tk.X, anchor=tk.N)
        preset_title_label = ttk.Label(preset_title_frame, text="Preset")
        preset_title_label.pack(side=tk.LEFT, padx=5, pady=5)

        def fetch_preset():
            presets = []
            preset_files = glob.glob(f"{os.path.dirname(os.path.abspath(__file__))}/preset/*.json")
            for p in preset_files:
                p = re.sub(r"/.*/", "", p)
                p = re.sub(r"\.json", "", p)
                presets.append(p)
            pre_load_cmb.config(values=presets)

        def button_save_preset():
            preset_name = pre_save_var.get()
            if preset_name and not preset_name.isspace():
                preset_filename = f"{os.path.dirname(os.path.abspath(__file__))}/preset/{preset_name}.json"
                if not os.path.isfile(preset_filename) or messagebox.askokcancel(title="Save Preset", message=f"Overwrite existing preset '{preset_name}'?"):
                    with open(preset_filename, 'w') as preset_file:

                        imageinfo_update()
                        preset_imageinfo = copy.deepcopy(imageinfo)
                        preset_imageinfo.freeze_params()
                        _, preset_imageinfo_params = preset_imageinfo.get_params()

                        storageinfo_update()
                        preset_storageinfo = copy.deepcopy(storageinfo)
                        preset_storageinfo.freeze_params()
                        _, preset_storageinfo_params = preset_storageinfo.get_params()

                        preset_content = {}
                        preset_content["imageinfo"] = preset_imageinfo_params
                        preset_content["storageinfo"] = preset_storageinfo_params
                        preset_json_string = json.dumps(preset_content, indent=4)
                        preset_file.write(preset_json_string)
                        fetch_preset()

        def button_load_preset():
            preset_name = pre_load_var.get()
            preset_filename = f"{os.path.dirname(os.path.abspath(__file__))}/preset/{preset_name}.json"
            if os.path.isfile(preset_filename):
                with open(preset_filename) as preset_file:
                    params = json.load(preset_file)
                    imageinfo.apply_params(params["imageinfo"])
                    storageinfo.apply_params(params["storageinfo"])
                    image_value_set()
                    storage_value_set()
                    #self.apply_params(self, params)

        pre_load_frame = ttk.Frame(fr_pre)
        pre_load_frame.pack(fill=tk.X, anchor=tk.N)
        pre_load_bt = ttk.Button(pre_load_frame, text="Load", command=button_load_preset)
        pre_load_bt.pack(side=tk.LEFT, padx=5, pady=5)
        pre_load_var = tk.StringVar()
        pre_load_cmb = ttk.Combobox(pre_load_frame,  text = 'null', values = ['eins', 'zwei', 'drei'], state = 'readonly' )
        pre_load_cmb.config(textvariable=pre_load_var)
        pre_load_cmb.pack(fill=tk.X, padx=5, expand=True)

        pre_save_frame = ttk.Frame(fr_pre)
        pre_save_frame.pack(fill=tk.X, anchor=tk.N)
        pre_save_bt = ttk.Button(pre_save_frame, text="Save", command=button_save_preset)
        pre_save_bt.pack(side=tk.LEFT, padx=5, pady=5)
        pre_save_var = tk.StringVar()
        pre_save_entry = ttk.Entry(pre_save_frame)
        pre_save_entry.config(textvariable=pre_save_var)
        pre_save_entry.pack(fill=tk.X, padx=5, expand=True)



        def button_ok():
            nonlocal ok 
            ok = True

            storageinfo_update()
            imageinfo_update()

            d.destroy()
            d.update()

        def button_cancel():
            nonlocal ok 
            ok = False

            d.destroy()
            d.update()

        bt_cancel = ttk.Button(fr, text="Cancel", command=button_cancel)
        bt_cancel.pack(side=tk.RIGHT, padx=5, pady=5)

        bt_ok = ttk.Button(fr, text="OK", command=button_ok)
        bt_ok.pack(side=tk.RIGHT)

        d.protocol("WM_DELETE_WINDOW", button_cancel)



        image_value_set()
        storage_value_set()
        fetch_preset()

        self.wait_window(d)

        return ok, storageinfo, imageinfo


    def dialog_tab_select_generic(self, select_count=0, name=None, description=None):
        tab_count = self.tab_control.index("end")

        tab_ids = self.tab_control.tabs()
        tab_names = []
        tab_vars = []

        res_images = None

        d = tk.Toplevel(self)

        fr = ttk.Frame(d)
        fr.master.title("Image Select")
        fr.style = ttk.Style()
        fr.style.theme_use("default")
        fr.pack(fill=tk.BOTH, expand=True)

        if name:
            fr_sec = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
            fr_sec.pack(fill=tk.BOTH, expand=True)

            fr_line = ttk.Frame(fr_sec)
            fr_line.pack(fill=tk.X, anchor=tk.N)
            label = ttk.Label(fr_line, text=name)
            label.pack(side=tk.LEFT, padx=5, pady=5)

        if description:
            fr_sec = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
            fr_sec.pack(fill=tk.BOTH, expand=True)

            fr_line = ttk.Frame(fr_sec)
            fr_line.pack(fill=tk.X, anchor=tk.N)
            label = ttk.Label(fr_line, text=f"Description:\n{description}")
            label.pack(side=tk.LEFT, padx=5, pady=5)
            
        if select_count > 0:
            fr_sec = ttk.Frame(fr, relief=tk.RAISED, borderwidth=1)
            fr_sec.pack(fill=tk.BOTH, expand=True)

            if tab_count > 0:
                tab_selected = self.tab_control.select()
                tab_selected = self.tab_control.index(tab_selected)

                for i in range(tab_count):
                    tab_content = self.tab_control.nametowidget(tab_ids[i]).nametowidget("!imagetab")
                    tab_names.append( f"Tab {i+1} - {tab_content.name}" )

                for i in range(select_count):
                    tab_var = tk.StringVar('')
                    tab_var.set( tab_names[tab_selected] )
                    tab_vars.append( tab_var )
                    fr_line = ttk.Frame(fr_sec)
                    fr_line.pack(fill=tk.X, anchor=tk.N)
                    label = ttk.Label(fr_line, text=f"Image {i+1}", width=15)
                    label.pack(side=tk.LEFT, padx=5, pady=5)
                    entry = ttk.Combobox(fr_line, text = tab_names[tab_selected], values = tab_names, state = 'readonly' )
                    entry.config(textvariable=tab_var)
                    entry.pack(fill=tk.X, padx=5, expand=True)
            else:
                fr_line = ttk.Frame(fr_sec)
                fr_line.pack(fill=tk.X, anchor=tk.N)
                label = ttk.Label(fr_line, text=f"No active images")
                label.pack(side=tk.LEFT, padx=5, pady=5)

        def button_ok():
            # update the image list
            nonlocal res_images
            if select_count > 0:
                if tab_count > 0:
                    res_images = []
                    for i in range(select_count):
                        tab_name = tab_vars[i].get()
                        tab_index = tab_names.index(tab_name)
                        tab_content = self.tab_control.nametowidget(tab_ids[tab_index]).nametowidget("!imagetab")
                        res_images.append(tab_content.img)
            d.destroy()
            d.update()

        def button_cancel():
            # set an invalid image list
            d.destroy()
            d.update()

        if tab_count > 0:
            bt_cancel = ttk.Button(fr, text="Cancel", command=button_cancel)
            bt_cancel.pack(side=tk.RIGHT, padx=5, pady=5)

        bt_ok = ttk.Button(fr, text="OK", command=button_ok)
        bt_ok.pack(side=tk.RIGHT)

        self.wait_window(d)

        return res_images


    def dialog_abs_diff_col(self):
        name="Absolute Image Difference on each Color Component"
        description = ( "The absolute difference for each color component between\n"
                        "two images is calculated and a result image is generated\n"
                        "Smaller differences resulting in small color values\n"
                        "Attention:\n"
                        "For images with more than 8 bit accuracty further LSBs\n"
                        "ignored for the result image\n" )
        images = self.dialog_tab_select_generic(select_count=2, name=name, description=description)
        if images and len(images) > 0:
            tab_image = HImage.OperationDiff(images, HImage.OPERATOR_DIFF_ABS_COLOR)
            tab_name = "Absolute Image Difference (color)"
            self.open_image_tab(tab_image, tab_name)


    def dialog_abs_diff_grey(self):
        name="Absolute Image Difference over all Color Components"
        description = ( "The absolute difference for each color component between\n"
                        "two images is calculated. The maximal difference values over\n"
                        "all color components generates a gray result image\n"
                        "Smaller differences resulting in small gray values\n"
                        "Attention:\n"
                        "For images with more than 8 bit accuracty further LSBs\n"
                        "ignored for the result image\n" )
        images = self.dialog_tab_select_generic(select_count=2, name=name, description=description)
        if images and len(images) > 0:
            tab_image = HImage.OperationDiff(images, HImage.OPERATOR_DIFF_ABS_ALL)
            tab_name = "Absolute Image Difference (grey)"
            self.open_image_tab(tab_image, tab_name)


    def dialog_rel_diff_col(self):
        name="Relative Image Difference on each Color Component"
        description = ( "The difference for each color component between two images\n"
                        "is calculated. The reslulting values are scaled according\n"
                        "to the maximal aberration and a 8bit colored result image\n"
                        "is generated. Positive differences are resulting\n"
                        "in brighter color values, negative image values in darker\n"
                        "values. Identical values are scalted to the value 128.\n" )
        images = self.dialog_tab_select_generic(select_count=2, name=name, description=description)
        if images and len(images) > 0:
            tab_image = HImage.OperationDiff(images, HImage.OPERATOR_DIFF_REL_COLOR)
            tab_name = "Relative Image Difference (color)"
            self.open_image_tab(tab_image, tab_name)


    def dialog_rel_diff_grey(self):
        name="Relative Image Difference over all Color Components"
        description = ( "The difference for each color component between two\n"
                        "images is calculated. The maximal difference values\n"
                        "over all color components generates 8bit gray result image\n"
                        "The reslulting values are scaled according to the maximal\n"
                        "aberration. Positive differences are resulting\n"
                        "in brighter color values, negative image values in darker\n"
                        "values. Identical values are scalted to the gray value 128.\n" )
        images = self.dialog_tab_select_generic(select_count=2, name=name, description=description)
        if images and len(images) > 0:
            tab_image = HImage.OperationDiff(images, HImage.OPERATOR_DIFF_REL_ALL)
            tab_name = "Relative Image Difference (grey)"
            self.open_image_tab(tab_image, tab_name)


    def dialog_file_open(self):
        filename = filedialog.askopenfilename()
        tab_image = HImage()
        ok = tab_image.open(file_name=filename, config_function=self.dialog_configure_image)
        if ok:
            tab_name = re.findall("([/].*[/])(.*)$", f"//{filename}")[0][1]
            self.open_image_tab(tab_image, tab_name)


    def dialog_not_implemented(self):
        messagebox.showinfo('Message','Not implemanted yet')




if __name__ == '__main__':
    arg_nosplash = False
    arg_files = []

    for arg in sys.argv:
        if arg == __file__:
            pass
        elif arg == "nosplash":
            arg_nosplash = True
        else:
            filename = arg
            if not os.path.isabs(filename):
                filename = f"{os.getcwd()}/{filename}"
            if os.path.isfile(filename):
                arg_files.append(filename)

    him_view = HIMView(nosplash=arg_nosplash)

    for f in arg_files:
        him_view.open_image_tab(HImage(f), re.findall("([/].*[/])(.*)$", f"//{f}")[0][1])

    him_view.mainloop()
