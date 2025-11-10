"""namespace.py

global namespace manager
"""

from rdflib import Graph
from rdflib.namespace import NamespaceManager

NSM = NamespaceManager(Graph(), bind_namespaces="none")
