"""System clock and identifier adapters.

References:
- https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
- https://docs.python.org/3/library/uuid.html#uuid.uuid4
"""

import time
import uuid


class SystemClock:
    def now(self) -> float:
        return time.time()


class SystemIdentifierGenerator:
    def new(self) -> str:
        return str(uuid.uuid4())
