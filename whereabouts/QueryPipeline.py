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
        Creates a string representation of all the CTEs for the query steps in the pipeline. Each CTE is defined by the createCTE method of the QueryStep class.

        Returns:
            A string representing the combined CTE definitions for all query steps in the pipeline.
        """
        return "".join([step.createCTE() for step in self.steps])

    def execute(self, 
                parameters: list | None = None,
                verbose: bool = False) -> pd.DataFrame:
        """
        Executes all the query steps in the pipeline in sequence.

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
        full_query = self.createCTEs()

        if verbose:
            print("Executing the following query pipeline\n")
            print("---------------------------------------")

            max_len = max(len(step.step_name) for step in self.steps)
            for step_number, step in enumerate(self.steps, start=1):
                print(
                    f"{step_number:>2}. "
                    f"{step.step_name:<{max_len}} "
                    f"-> {step.step_description}"
                )
                # Print down arrow between steps
                if step_number < len(self.steps):
                    print("    ↓")
            print("---------------------------------------\n")

        results = self.con.sql(full_query).df()

        return results