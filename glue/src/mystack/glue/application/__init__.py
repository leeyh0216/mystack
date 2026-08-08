"""Glue Data Catalog use cases.

Reference: https://docs.aws.amazon.com/glue/latest/dg/catalog-and-crawler.html
"""

from mystack.glue.application.service import CatalogApplication, CatalogPolicy
from mystack.glue.application.table_optimizer import TableOptimizerPolicy

__all__ = ["CatalogApplication", "CatalogPolicy", "TableOptimizerPolicy"]
