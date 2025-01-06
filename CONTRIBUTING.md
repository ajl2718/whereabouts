# How to contribute

It would be great to have others contribute to this [whereabouts](https://https://github.com/ajl2718/whereabouts) particularly those who have experience working with geospatial data from countries outside of Australia. This document
explains how you can contribute to the project.

Firstly:

  * Familiarise yourself with the [codebase](https://https://github.com/ajl2718/whereabouts)
  * If you have any questions, first consult the [documentation](https://whereabouts.readthedocs.io/en/latest/)

## Testing

I have created some unit tests and more are being added to ensure that any changes don't break existing features.

## Submitting changes

Please send a [GitHub Pull Request to whereabouts](https://github.com/ajl2718/whereabouts/pull/new/master) with a clear list of what you've done (read more about [pull requests](http://help.github.com/pull-requests/)). When you send a pull request, we will love you forever if you include RSpec examples. We can always use more test coverage. Please follow our coding conventions (below) and make sure all of your commits are atomic (one feature per commit).

Always write a clear log message for your commits. One-line messages are fine for small changes, but bigger changes should look like this:

    $ git commit -m "A brief summary of the commit
    > 
    > A paragraph describing what changed and its impact."

## Coding conventions

Start reading the code to get an idea of the coding conventions for the project.

  * We indent using two spaces (soft tabs)
  * We ALWAYS put spaces after list items and method parameters (`[1, 2, 3]`, not `[1,2,3]`), around operators (`x += 1`, not `x+=1`), and around hash arrows.
  * This is open source software. Consider the people who will read your code, and make it look nice for them. 

Thanks,
Alex Lee
