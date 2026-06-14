from __future__ import annotations

from duckdb import DuckDBPyConnection
import pandas as pd

from .QueryStep import QueryStep


class QueryPipeline:
    """
    A pipeline of query steps that can be executed in sequence. Each step is an instance of the QueryStep class.

    Attributes:
        steps (list[QueryStep]): A list of QueryStep instances that make up the pipeline.
    """
    def __init__(self, 
                 con: DuckDBPyConnection,
                 steps: list[QueryStep]):
        self.con = con
        self.steps = steps

    def add_step(self, step: QueryStep):
        """
        Adds a new QueryStep to the pipeline.

        Args:
            step (QueryStep): The QueryStep instance to be added to the pipeline.
        """
        self.steps.append(step)

    def remove_step(self, step_name: str):
        """
        Removes a QueryStep from the pipeline based on its name.

        Args:
            step_name (str): The name of the QueryStep to be removed from the pipeline.
        """
        self.steps = [step for step in self.steps if step.step_name != step_name]

    def createCTEs(self):
        """
        Creates a string representation of all the CTEs for the non-direct-execution
        query steps in the pipeline.

        The first and last CTE steps are automatically detected — the first
        non-direct step emits the ``WITH`` clause and the last appends the
        final ``SELECT``.  Any ``starting_step`` / ``ending_step`` flags set
        on individual steps are ignored.

        Returns:
            A string representing the combined CTE definitions for all query steps in the pipeline.
        """
        cte_steps = [step for step in self.steps if not getattr(step, 'direct_execution', False)]
        parts: list[str] = []
        for idx, step in enumerate(cte_steps):
            is_first = idx == 0
            is_last = idx == len(cte_steps) - 1
            parts.append(step.createCTE(is_first=is_first, is_last=is_last))
        return "".join(parts)

    def _execute_direct_steps(self, verbose: bool = False) -> None:
        """Execute all direct_execution steps in order."""
        for step in self.steps:
            if getattr(step, 'direct_execution', False):
                if verbose:
                    print(f"  [direct] {step.step_name} -> {step.step_description}")
                if isinstance(step.input_table_names, dict):
                    sql = step.query_template.format(**step.input_table_names)
                else:
                    sql = step.query_template
                self.con.execute(sql)

    def _print_pipeline(self) -> None:
        """Print a summary of all pipeline steps."""
        print("Executing the following query pipeline\n")
        print("---------------------------------------")
        max_len = max(len(step.step_name) for step in self.steps)
        for step_number, step in enumerate(self.steps, start=1):
            marker = "[direct]" if getattr(step, 'direct_execution', False) else "[CTE]   "
            print(
                f"{step_number:>2}. {marker} "
                f"{step.step_name:<{max_len}} "
                f"-> {step.step_description}"
            )
            if step_number < len(self.steps):
                print("    ↓")
        print("---------------------------------------\n")

    def execute(self, 
                parameters: list | None = None,
                verbose: bool = False) -> pd.DataFrame:
        """
        Executes all the query steps in the pipeline in sequence.
        Direct-execution steps run first, then the CTE chain is built and executed.

        Parameters
        ----------
        parameters : list, optional
            Parameters to pass to the SQL query.
        verbose : bool, optional
            If True, print step-by-step details of the pipeline. Defaults to False.

        Returns
        -------
        results : pd.DataFrame
            The results of the pipeline execution.
        """
        if verbose:
            self._print_pipeline()

        self._execute_direct_steps(verbose=verbose)
        full_query = self.createCTEs()
        results = self.con.sql(full_query).df()

        return results
    
    def execute_as_table(self, 
                         table_name: str,
                         parameters: list | None = None,
                         verbose: bool = False):
        """
        Executes the query pipeline and saves the results as a new table in the database.
        Direct-execution steps run first, then the CTE chain is materialised as a table.

        Parameters
        ----------
        table_name : str
            The name of the table to save the results to.
        parameters : list, optional
            Parameters to pass to the SQL query.
        verbose : bool, optional
            If True, print step-by-step details of the pipeline. Defaults to False.
        """
        if verbose:
            self._print_pipeline()

        self._execute_direct_steps(verbose=verbose)
        full_query = self.createCTEs()
        self.con.sql(f"CREATE TABLE {table_name} AS {full_query}")