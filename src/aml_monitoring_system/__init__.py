# Import all models here so Alembic autogenerate and SQLAlchemy
# relationship resolution can find every mapped class in one place.
from app.models.user         import User          # noqa: F401
from app.models.transaction  import Transaction   # noqa: F401
from app.models.alert        import Alert         # noqa: F401
from app.models.risk_score   import RiskScore     # noqa: F401
from app.models.pep_profile  import PEPProfile    # noqa: F401
from app.models.graph_node   import GraphNode     # noqa: F401
