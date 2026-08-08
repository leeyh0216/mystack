"""Glue Data Catalog use cases.

Reference: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
"""

from .service import CatalogApplication, CatalogPolicy

__all__ = ["CatalogApplication", "CatalogPolicy"]
