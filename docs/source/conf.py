# Configuration file for the Sphinx documentation builder.
import os
import sys
current_dir = os.path.abspath(os.path.dirname(__file__))

# Get the absolute path to the project root directory
project_root = os.path.abspath(os.path.join(current_dir, '../../'))

# Add the whereabouts directory to sys.path
sys.path.insert(0, os.path.join(project_root, 'whereabouts'))

# -- Project informatio n

project = 'whereabouts'
copyright = '2024, Alex Lee'
author = 'Alex Lee'

release = '0.3.13'
version = "0.3.13"

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

# -- Options for EPUB output
epub_show_urls = 'footnote'