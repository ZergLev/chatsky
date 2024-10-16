import os
import sys
import re
import importlib.metadata
import importlib.util
from pathlib import Path

import pydata_sphinx_theme

# -- Path setup --------------------------------------------------------------

sys.path.append(os.path.abspath("."))
from utils.notebook import py_percent_to_notebook  # noqa: E402
from sphinx_polyversion.api import load
from sphinx_polyversion.git import GitRef

# -- Project information -----------------------------------------------------

current = [None]
polyversion_build = os.getenv("POLYVERSION_BUILD", default="False")
if polyversion_build == "True":
    data = load(globals())  # adds variables `current` and `revisions`
    current: GitRef = data['current']

_distribution_metadata = importlib.metadata.metadata('chatsky')

project = _distribution_metadata["Name"]
copyright = "2022 - 2024, DeepPavlov"
author = "DeepPavlov"
release = _distribution_metadata["Version"]


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.extlinks",
    "sphinxcontrib.katex",
    "sphinx_copybutton",
    "sphinx_favicon",
    "sphinx_autodoc_typehints",
    "nbsphinx",
    "sphinx_gallery.load_style",
    "IPython.sphinxext.ipython_console_highlighting",
]

suppress_warnings = ["image.nonlocal_uri"]
source_suffix = ".rst"
master_doc = "index"

version = re.match(r"^\d\.\d.\d", release).group()
language = "en"

pygments_style = "default"

add_module_names = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["*.py", "utils/*.py", "**/_*.py", "_misc/*.py"]

html_short_title = "None"

# -- Options for HTML output -------------------------------------------------

sphinx_gallery_conf = {
    "promote_jupyter_magic": True,
}

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_show_sourcelink = False

autosummary_generate_overwrite = False

if polyversion_build == "True":
    doc_version = str(current[0]) + '/'
else:
    doc_version = os.getenv("BRANCH_NAME", default="")
    if doc_version != "":
        doc_version = doc_version + '/'
# Finding tutorials directories
nbsphinx_custom_formats = {".py": py_percent_to_notebook}
nbsphinx_prolog = f"""
:tutorial_name: {{{{ env.docname }}}}
:doc_version: {doc_version}
"""

html_logo = "_static/images/Chatsky-full-dark.svg"

nbsphinx_thumbnails = {
    "tutorials/*": "_static/images/Chatsky-min-light.svg",
}

html_context = {
    "github_user": "deeppavlov",
    "github_repo": "chatsky",
    "github_version": "master",
    "doc_path": "docs/source",
}

html_css_files = [
    "css/custom.css",
]

version_data = version
# Checking for dev before passing version to switcher
if polyversion_build == "True":
    if current[0] == "dev":
        version_data = "dev"
        # Possible to-do: show the warning banner for latest(unstable) version.

# Version switcher url
switcher_url = "https://zerglev.github.io/chatsky/switcher.json"

# Removing version switcher from local doc builds. There is no local multi-versioning.
# Instead, this allows the person to use their own switcher if they need it for some reason.
LOCAL_BUILD = os.getenv('LOCAL_BUILD', default="True")
if LOCAL_BUILD:
    switcher_url = "./_static/switcher.json"

# Theme options
html_theme_options = {
    "header_links_before_dropdown": 5,
    "icon_links": [
        {
            "name": "DeepPavlov Forum",
            "url": "https://forum.deeppavlov.ai",
            "icon": "_static/images/logo-deeppavlov.svg",
            "type": "local",
        },
        {
            "name": "Telegram",
            "url": "https://t.me/DeepPavlovDreamDiscussions",
            "icon": "fa-brands fa-telegram",
            "type": "fontawesome",
        },
        {
            "name": "GitHub",
            "url": "https://github.com/deeppavlov/chatsky",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
    "secondary_sidebar_items": ["page-toc", "source-links", "example-links"],
    "switcher": {
        "json_url": switcher_url,
        "version_match": version_data,
    },
    "navbar_persistent": ["search-button.html", "theme-switcher.html"],
    "navbar_end": ["version-switcher.html", "navbar-icon-links.html"],
    "show_version_warning_banner": True,
}

favicons = [
    {"href": "images/Chatsky-min-light.svg"},
]


autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "private-members": True,
    "special-members": "__call__",
    "member-order": "bysource",
    "exclude-members": "_abc_impl, model_fields, model_computed_fields, model_config",
}


def setup(_):
    # TODO: Import for old versions differently (it's unfinished now)
    #  Check if a given version is less than v0.9.0 via poly.py functions and/or new filters.
    #  Version v0.10.0 would show as less than v0.9.0, a mistake.
    #  Would be nice if there was a good way to check this, cause poly.py won't be in the old files, I think.
    #  Of course, it could be added, but that seems a bit invasive.
    # TODO: I think setup() doesn't launch, even though the old_conf.py file is there.
    print(version)
    print(str(version))
    if polyversion_build == "True":
        if current[0] != "dev" and str(version) < "v0.9.0":
            print("current[0] is", current[0])
            print("building old version")
            root_dir = Path(__file__).parent
            print(root_dir / "old_conf.py")
            print("old_conf.py path is copied correctly:", os.path.isfile(root_dir / "old_conf.py"))
            spec = importlib.util.spec_from_file_location("setup", root_dir / "old_conf.py")
            setup_module = importlib.util.module_from_spec(spec)
            sys.modules["setup"] = setup_module
            spec.loader.exec_module(setup_module)
            setup_module.setup(_)
            # Or this could just be
            # from .old_conf import setup
            # setup(_)
    else:
        from setup import setup
        setup()
