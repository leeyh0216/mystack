"""System clock adapter.

Timestamp shape reference: https://docs.aws.amazon.com/glue/latest/webapi/API_Table.html
"""

import time


class SystemClock:
    def now(self) -> float:
        return time.time()
