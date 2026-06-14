from __future__ import annotations


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
                 direct_execution: bool = False,
                 step_name: str | None = None, 
                 step_description: str | None = None):
        self.query_template = query_template
        self.output_table_name = output_table_name
        self.input_table_names = input_table_names
        self.starting_step = starting_step
        self.ending_step = ending_step
        self.direct_execution = direct_execution
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
    
    def createCTE(self, *, is_first: bool | None = None, is_last: bool | None = None):
        """
        Creates a Common Table Expression (CTE) for this query step.

        Parameters
        ----------
        is_first : bool | None
            Override for whether this step starts the ``WITH`` clause.
            When *None* (default) falls back to ``self.starting_step``.
        is_last : bool | None
            Override for whether this step appends the final ``SELECT``.
            When *None* (default) falls back to ``self.ending_step``.

        Returns
        -------
        str
            A string representing the CTE definition for this query step.
        """
        starting = self.starting_step if is_first is None else is_first
        ending = self.ending_step if is_last is None else is_last

        formatted = self.query_template.format(**self.input_table_names)
        if starting and ending:
            return f"""WITH {self.output_table_name} AS (\t{formatted}\n)\nSELECT * FROM {self.output_table_name}""".strip()
        elif starting:
            return f"""WITH {self.output_table_name} AS (\t{formatted}\n)""".strip()
        elif ending:
            return f""",\n{self.output_table_name} AS (\t{formatted}\n)\nSELECT * FROM {self.output_table_name}""".strip()
        else:
            return f""",\n{self.output_table_name} AS (\t{formatted}\n)""".strip()
        
def query_step(
    query_template: str,
    output_table_name: str,
    input_table_names: str | dict[str, str] | None = None,
    starting_step: bool = False,
    ending_step: bool = False,
    direct_execution: bool = False,
    step_name: str | None = None,
    step_description: str | None = None,
) -> QueryStep:
    """
    Factory function that creates a QueryStep from a SQL template string.

    Parameters
    ----------
    query_template : str
        The SQL query template with ``{placeholder}`` references to input tables.
    output_table_name : str
        The name of the CTE / output table produced by this step.
    input_table_names : str | dict[str, str] | None
        Mapping of placeholder names to actual table names used in the query template.
        Defaults to an empty dict when *None*.
    starting_step : bool
        Whether this is the first step in the pipeline (generates the ``WITH`` clause).
        In most cases this can be left *False* because ``QueryPipeline.createCTEs``
        auto-detects the first CTE step.
    ending_step : bool
        Whether this is the last step (appends a final ``SELECT`` from the CTE).
        In most cases this can be left *False* because ``QueryPipeline.createCTEs``
        auto-detects the last CTE step.
    step_name : str | None
        A human-readable name for the step. Defaults to ``output_table_name``.
    step_description : str | None
        A human-readable description of what the step does.

    Returns
    -------
    QueryStep
        A ``QueryStep`` instance.

    Examples
    --------
    >>> step = query_step(
    ...     query_template="SELECT * FROM {orders} WHERE status != 'cancelled'",
    ...     output_table_name="filtered_orders",
    ...     input_table_names={"orders": "raw_orders"},
    ...     step_name="Filter Orders",
    ...     step_description="Removes cancelled orders from the dataset",
    ... )
    >>> print(step)
    QueryStep(name=Filter Orders, description=Removes cancelled orders from the dataset)
    """
    if input_table_names is None:
        input_table_names = {}

    return QueryStep(
        query_template=query_template,
        output_table_name=output_table_name,
        input_table_names=input_table_names,
        starting_step=starting_step,
        ending_step=ending_step,
        direct_execution=direct_execution,
        step_name=step_name,
        step_description=step_description,
    )
