from typing import Annotated, Final

from pydantic import Field

# Entero de 64 bits con signo: el INTEGER de SQLite y el bigint de PostgreSQL.
MAX_SQL_INTEGER: Final = 2**63 - 1

# Todo id que llega del cliente: uno fuera de rango no debe llegar al driver.
Id = Annotated[int, Field(ge=1, le=MAX_SQL_INTEGER)]
