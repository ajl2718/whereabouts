class WhereaboutsError(Exception):
    """Base class for all Whereabouts exceptions."""

class InvalidDatabaseError(WhereaboutsError):
    pass

class GeocodeError(WhereaboutsError):
    pass