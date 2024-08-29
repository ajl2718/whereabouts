Contributing to the Project
===========================

Contributions to whereabouts are welcome.

Whether you are fixing bugs, adding new features, or improving documentation, additional contributors can help to improve the project.

This guide will help you get started with making contributions to our project.

Getting Started
---------------

1. **Fork the Repository**: Start by forking the main repository to your own GitHub account. This will create a copy of the project where you can freely make changes.

2. **Clone Your Fork**: Clone the forked repository to your local machine using the following command:

.. code-block:: console

   $ https://github.com/your-username/your-forked-repo.git


3. **Set Up the Environment**: Install any necessary dependencies by following the instructions in the `README.md`. Ensure that you can run the project and that all tests pass before making any changes.

4. **Create a New Branch**: Before you start working, create a new branch off the `main` branch to keep your changes organized:

.. code-block:: console

    $ git checkout -b feature/your-feature-name


Making Changes
--------------

1. **Code Style**: Ensure your code adheres to the project's coding style, following the existing code structure is a good start.

2. **Write Tests**: If you are adding new features or fixing bugs, please include appropriate tests in order to maintain the quality of the project and prevents future issues.

3. **Document Your Changes**: If your contribution affects the public API, be sure to update the documentation. 

Submitting Your Contribution
----------------------------

1. **Commit Your Changes**: Once you have completed your work, commit your changes with a clear and descriptive message:

.. code-block:: console

    $ git commit -m "Add feature: description of your feature or fix"


2. **Push to Your Fork**: Push the changes to your forked repository on GitHub:

.. code-block:: console 

    $ git push origin feature/your-feature-name


3. **Create a Pull Request**: Navigate to the main repository on GitHub and create a pull request (PR) from your fork. Provide a clear title and description of your changes. If your PR is related to an open issue, reference the issue number in the description.

Review Process
--------------

Once you have submitted your pull request, it will be reviewed by one or more of the project maintainers. They may request changes or provide feedback. Please be responsive to any comments and update your pull request as needed.

After your pull request has been approved, it will be merged into the `main` branch.