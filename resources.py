"""Locating files that ship with the app, from source or from a PyInstaller build."""
import os
import sys


def app_dir():
    """Folder the app's own files live in.

    PyInstaller unpacks bundled data to sys._MEIPASS; from source it is the
    folder holding this file. Never use the working directory: it is wherever
    the app happened to be launched from (often "/" for a double-clicked app).
    """
    return getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))


def resource_path(relative):
    """Absolute path of a bundled file such as "icon.ico"."""
    return os.path.join(app_dir(), relative)
