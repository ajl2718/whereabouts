from __future__ import annotations

import functools
from collections.abc import Callable


class QueryStep:
    """
    A single query as part of a data processing pipeline.

    Each step has a name, a description, and a SQL query template that
    can be composed into a CTE chain and executed against a DuckDB connection.

    Attributes
    ----------
    query_template : str
        The SQL query template with ``{placeholder}`` references to input tables.
    output_table_name : str
        The name of the CTE / output table produced by this step.
    input_table_names : str | dict[str, str]
        Mapping of placeholder names to actual table names used in the query template.
    starting_step : bool
        Whether this is the first step in the pipeline (generates the ``WITH`` clause).
    ending_step : bool
        Whether this is the last step (appends a final ``SELECT`` from the CTE).
    step_name : str
        A human-readable name for the step.
    step_description : str
        A human-readable description of what the step does.
    """
    def __init__(self, 
                 query_template: str,
                 output_table_name: str,
                 input_table_names: str | dict[str, str],
                 starting_step: bool = False,
                 ending_step: bool = False,
                 step_name: str | None = None, 
                 step_description: str | None = None):
        self.query_template = query_template
        self.output_table_name = output_table_name
        self.input_table_names = input_table_names
        self.starting_step = starting_step
        self.ending_step = ending_step
        self.step_name = step_name if step_name else output_table_name
        self.step_description = step_description if step_description else f"Query step for {output_table_name}"
        self.validate_sql_and_mappings(query_template, input_table_names, output_table_name)

    @staticmethod
    def validate_sql_and_mappings(query_template: str, 
                                  input_table_names: str | dict[str, str],
                                  output_table_name: str) -> bool:
        """Validates that the input and output table names are correctly referenced in the SQL query."""

        # Check if all input table names are referenced in the SQL query
        if isinstance(input_table_names, dict):
            input_table_names = input_table_names.keys()
        for input_table_name in input_table_names:
            if f'{{{input_table_name}}}' not in query_template:
                raise ValueError(f"Input table name '{input_table_name}' is not referenced in the SQL query.")
        if output_table_name in input_table_names:
            raise ValueError(f"Output table name '{output_table_name}' cannot be the same as any of the input table names.")
        if output_table_name is None:
            raise ValueError("Output table name cannot be None.")
        return True
    
    def __str__(self):
        return f"QueryStep(name={self.step_name}, description={self.step_description})"
    
    def createCTE(self):
        """
        Creates a Common Table Expression (CTE) for this query step. The CTE is named after the step name and contains the SQL query of this step.

        Returns:
            A string representing the CTE definition for this query step.
        """
        if self.starting_step:
            return f"""WITH {self.output_table_name} AS (\t{self.query_template.format(**self.input_table_names)}\n)""".strip()
        elif self.ending_step:
            return f""",\n{self.output_table_name} AS (\t{self.query_template.format(**self.input_table_names)}\n)\nSELECT * FROM {self.output_table_name}""".strip()
        else:
            return f""",\n{self.output_table_name} AS (\t{self.query_template.format(**self.input_table_names)}\n)""".strip()
        
def query_step(
    output_table_name: str,
    input_table_names: str | dict[str, str],
    starting_step: bool = False,
    ending_step: bool = False,
    step_name: str | None = None,
    step_description: str | None = None,
) -> Callable:
    """
    Decorator that transforms a function returning a SQL string into a QueryStep instance.

    The decorated function should return a SQL query template string with
    ``{placeholder}`` references matching the keys in ``input_table_names``.

    Parameters
    ----------
    output_table_name : str
        The name of the CTE / output table produced by this step.
    input_table_names : str | dict[str, str]
        Mapping of placeholder names to actual table names used in the query template.
    starting_step : bool
        Whether this is the first step in the pipeline (generates the ``WITH`` clause).
    ending_step : bool
        Whether this is the last step (appends a final ``SELECT`` from the CTE).
    step_name : str | None
        A human-readable name for the step. Defaults to ``output_table_name``.
    step_description : str | None
        A human-readable description of what the step does.

    Returns
    -------
    QueryStep
        A ``QueryStep`` instance built from the decorated function's returned SQL string.

    Examples
    --------
    Basic usage — function returns a SQL template string:

    >>> @query_step(
    ...     output_table_name="filtered_orders",
    ...     input_table_names={"orders": "raw_orders"},
    ...     starting_step=True,
    ...     step_name="Filter Orders",
    ...     step_description="Removes cancelled orders from the dataset",
    ... )
    ... def filtered_orders():
    ...     return "SELECT * FROM {orders} WHERE status != 'cancelled'"

    The decorator replaces the function with a ready-to-use ``QueryStep``:

    >>> print(filtered_orders)
    QueryStep(name=Filter Orders, description=Removes cancelled orders from the dataset)
    >>> print(filtered_orders.createCTE())
    WITH filtered_orders AS (    SELECT * FROM raw_orders WHERE status != 'cancelled'
    )

    Chaining steps into a pipeline:

    >>> @query_step(
    ...     output_table_name="aggregated_orders",
    ...     input_table_names={"filtered_orders": "filtered_orders"},
    ...     ending_step=True,
    ...     step_name="Aggregate Orders",
    ...     step_description="Sums order values per customer",
    ... )
    ... def aggregated_orders():
    ...     return '''
    ...         SELECT customer_id, SUM(amount) AS total
    ...         FROM {filtered_orders}
    ...         GROUP BY customer_id
    ...     '''

    >>> pipeline_sql = filtered_orders.createCTE() + aggregated_orders.createCTE()
    >>> print(pipeline_sql)
    WITH filtered_orders AS (    SELECT * FROM raw_orders WHERE status != 'cancelled'
    )
    ,
    aggregated_orders AS (        SELECT customer_id, SUM(amount) AS total
            FROM filtered_orders
            GROUP BY customer_id
        
    )
    SELECT * FROM aggregated_orders
    """

    def decorator(func: Callable) -> "QueryStep":
        query_template = func()

        if not isinstance(query_template, str):
            raise TypeError(
                f"@query_step expects the decorated function '{func.__name__}' "
                f"to return a str, got {type(query_template).__name__!r} instead."
            )

        resolved_name = step_name or func.__name__
        resolved_description = step_description or func.__doc__

        step = QueryStep(
            query_template=query_template,
            output_table_name=output_table_name,
            input_table_names=input_table_names,
            starting_step=starting_step,
            ending_step=ending_step,
            step_name=resolved_name,
            step_description=resolved_description,
        )

        # Preserve the original function's metadata on the QueryStep for
        # introspection (e.g. help(), IDE tooling).
        functools.update_wrapper(step, func)
        return step

    return decorator
