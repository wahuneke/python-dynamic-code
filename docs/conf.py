from importlib import metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.

project = "python-dynamic-code"
copyright = "2023, Bill Huneke"
author = "Bill Huneke"

release = metadata.version(project)
# The short X.Y version.
version = ".".join(release.split(".")[:2])


language = "en"

pygments_style = "sphinx"
html_logo = "static/img/python_dynamic_code.png"
html_theme = "alabaster"
html_theme_options = {
    # "logo": "img/python_dynamic_code.png",
    "description": "Runtime, fast path, optimizations",
    "github_user": "wahuneke",
    "github_repo": "python-dynamic-code",
    "github_button": "true",
    "github_banner": "true",
    "github_type": "star",
    "badge_branch": "main",
    "page_width": "1080px",
    "sidebar_width": "300px",
    "fixed_sidebar": "false",
}
html_sidebars = {"**": ["about.html", "localtoc.html", "relations.html", "searchbox.html"]}
html_static_path = ["static"]

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = []

autodoc_member_order = "bysource"

nitpicky = False
nitpick_ignore = ["py:class"]

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "python-dynamic-code",
        "python-dynamic-code Documentation",
        author,
        "python-dynamic-code",
        "One line description of project.",
        "Miscellaneous",
    )
]

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/latest", None),
    "setuptools": ("https://setuptools.pypa.io/en/latest", None),
    "tox": ("https://tox.wiki/en/latest", None),
    "devpi": ("https://devpi.net/docs/devpi/devpi/stable/+doc/", None),
    "kedro": ("https://docs.kedro.org/en/latest/", None),
}
