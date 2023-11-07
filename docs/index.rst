``Python Dynamic Code``
==============================

**Runtime, fast path, optimizations**

############
What is it?
############

**NOTICE**: this project is experimental - its use in production projects should be very carefully considered

``Python Dynamic Code (PDC)`` can be used to accelerate a key section of code ("fastpath")
in cases where standard Python optimization methods cannot be applied or might introduce too much
complexity.

****************************
What programs might benefit?
****************************
The ``PDC`` system is well suited for complex applications that have a small, isolated
block of code that is its *fastpath*. And, if the fastpath changes its shape
depending on some runtime input, it may be well suited for runtime, dynamic
optimization.

Will it work in my fastpath?
----------------------------

The ``PDC`` may be applied to accelerate a function where:

* function parameters include

  - some subset of data which rarely changes, but which is expensive to access or which
    requires some expensive transformation operation
  - other inputs with constantly changing values, and these are the values you want
    to process quickly because the function will be called repeatedly with new values
    each time

* significant blocks of code may be completely dormant in most cases, but need to be present
  for rare cases, and they depend on slow-changing inputs

What types of optimizations?
****************************
After program startup, after configuration or user selections, just before running the program's *main loop*:

* Your fastpath code looks up the same keys or attributes in some dynamic (runtime / user
  populated) mapping over and over again, even though the values never or almost never
  change?  ``PDC`` might be able to help you by rewriting your program so that the values
  appear in the code as constants, **precalculated**. Eliminating multiple *dictionary* lookups
  for every run of the fast path may lead to significant speed ups.

Minor optimizations:

* Does the fastpath include large blocks of code that become dormant depending on runtime
  settings?  Those blocks can be **dropped** completely out of the program, eliminating unnecessary
  comparisons and jumps in addition to making the final block of code smaller (theoretically, improving *locality of
  reference*).
* If your fastpath code has an inner loop that iterates over some short list of items provided
  by the user at runtime, we can **unroll** that loop. Unrolling a loop may make your code
  run faster because it eliminates comparisons and jumps.  In turn, this will (theoretically) improve instruction
  prefetch.  Coincidentally, this also undoes the above benefit, making your code *bigger* :)

What are the risks?
*******************
This is a brand new project, originating mostly out of personal curiosity. If other people make use of it and submit
issues, this section may be updated.  For now, just off the top of my head:

* This library ultimately utilizes ``python exec`` in order to do what it does. This function introduces behavior that
  does not arise very often in typical Python projects

  - Depending on how ``PDC`` is being used, there is potential for the introduction of **arbitrary code execution**
    security vulnerabilities
  - By its nature, this library builds and runs brand new Python code. Consequently, errors either on the part of the
    library user or its author(s) could (theoretically) lead to unexpected execution of commands leading to data loss,
    or other 'high impact' outcomes

* This library is **experimental** and brand new (as of October 2023). As such, its code is not 'field tested' and does
  not have the benefit of multiple project users uncovering defects


##################
How do you use it?
##################
Your existing fast path code remains unchanged. The ``PDC`` tool changes your existing code
via code annotations that are added to the code as comments.  After this, a decision must be
made about **when** in the program flow the optimization will happen (and also, when re-optimization should be
calculated, as in the case where configuration changes).

How does it work?
*****************
Your annotated source code is read and portions of the code are executed along with new
instructions which take values from the code run and use them to generate a brand new,
optimized fast path.

The brand new fast path Python code is then run through the Python compiler, and the result
is executed in place of the original fastpath code, whenever it is needed in normal program
flow.  If, during program flow, a configuration changes significantly enough that the fastpath
should be recalculated, ``PDC`` takes care of re-applying the original analysis, recompiling
the generated Python, and a newly-optimized fastpath is ready to be used again.

For each DynamicCodeBuilder attached to a function or instance, the following three steps
will occur, at different times:
#. **At start time** (ie, when Python first loads your module) - the source code (with PDC 'annotations') is read and
parsed.  A block of 'conversion code' is generated
#. At fast path runtime **if slow params have changed** - the conversion code is executed. In combination with the
values found in the 'slow params', the conversion code generates a block of 'exec code'.
#. At fast path runtime **every time** - the exec code is executed.
Remember: the 'exec code' in this case is the optimized fast path code.  It was created by running the
'conversion code' and represents the streamlined version of the original fast path code.  It
will be _optimized_ for the current values of the 'slow params'.

Important features
******************
* During troubleshooting and testing, ``PDC`` can log all generated code for manual review and
  analysis
* While integration does require adding some code to your project, fastpath code can remain
  (semantically) unchanged.  During testing and benchmarking, ``PDC`` can easily activate the
  original functionality.  This facilitates **correctness testing** which compares optimized
  output to original output (to confirm that it is exacly identical).

Examples of use
****************

A video game
------------
The game engine in a first person shooter has a lot of work to do: keeping track of positions
and behavior of the player, adversaries, and projectiles, calculating an adversary's next move (AI),
etc.  Different player levels may have vastly different needs, some levels using some features
and other levels using other game play features.

Using ``PDC`` the game engine's main processing loop can have branches and cases completely
removed while the "level is loading". Likewise, specific instructions or data from the level
can be directly inserted into the code, eliminating the need to perform some repeated dictionary
and attribute lookups.

A plugin library
----------------
``PDC`` was originally conceived as a way to potentially optimize the Python library *pluggy*.
The plugin library allows for 'plugins' to be registered at runtime and for these plugins
to provide hooks which must then be called during the handling of application events. In some
cases, the list of plugins may be very long.  Preparing the proper call arguments for each plugin
before calling it takes a non-negligible amount of time.  The plugin library would prefer to
be as 'thin' as possible, guaranteeing the least disturbance to application performance while
still providing necessary features for useful plugin behavior.

Using ``PDC``, the plugin library could have the calls to plugins rewritten so that argument
values are accessed more directly without requiring dictionary lookups and temporary argument
tuples to be built.

Terms and Concepts
-------------------
The following terms may be used in explaining how to use ``PDC``:

compilation
    In this context, 'compilation' is the program step, during runtime, when the original source
    code, written by the programmer, is converted into new Python code using information accumulated
    during runtime.

slow params
    This is shorthand for the set portion of the parameters to the fast path function which are
    not expected to change very frequently.  These parameters are (optionally) monitored for change
    and when they do change, the fast path (`exec code`) code is recompiled.

code annotations
    In this context, 'code annotations' are instructions that are added into existing, working, Python
    code indicating how the code should be transformed during compilation.

exec block
    This is the final, runnable, code object which can now be run as the new 'fast path' in your code.
    The ``PDC`` library can help with keeping track of whether this code is 'fresh' and whether / when
    it needs to be recompiled from scratch (because of a change in application data).

source code
    This will always refer to the original code, written by the programmer, which is processed by
    ``PDC``

conversion code
    When ``PDC`` runs, the first thing it does is convert the source code into new code which builds
    new fast path code by assembling and combining code bits into a string.  The conversion code is
    created without input from the application.  It is a one-to-one transformation using the source
    code and the ``PDC`` code annotations found within it.  This code is readable Python, generated
    only once at runtime, and is available for viewing through introspection.

exec code
    Once ``PDC`` has created the conversion code, and has application data to be used with it, the
    conversion code can be executed.  The output from this will be *exec code*.  This exec code is
    readable Python, it is *re-generated* infrequently, but whenever necessary due to change in
    application state, and the exec code is available for viewing through introspection.

code builder class
    For each fast path of code being processed by ``PDC``, there will be a specialized code builder
    class written by the user which will subclass the DynamicCodeBuilder class of the ``PDC`` library.

code runner
    The ``PDC`` DynamicCodeRunner class is used to wrap the fastpath function that is being optimized.
    It handles

Usage
------
In the following simple code segments, a variety of usage scenarios will be demonstrated.

A 'fastpath' code segment is prepared for optimization
===

F.A.Q.
-------

Aren't there usually better ways to pre-process and optimize input to a fast path?
    **Yes!** There usually is a better way. If you can find a better way for your situation,
    then please do not use this library. This library is intended to help in situations where
    you have looked and could not find a 'better way'.

Will this interfere with my ability to run the debugger on fast path code?
    It might! The library is crafted in such a way that it will do its best to work with debuggers.
    We recognize that this capability is important and will work to continuously improve in this area.

Will line numbers in back traces or loggers make any sense?
    Hopefully! As with the question about debuggers,we are doing our best to preserve this important
    tool in Python debugging.

Why did you make a library that messes with Python internals and complicates things?
    The techniques in this library have been demonstrated to provide potentially massive speedups, in
    a limited number of use cases. It does this with a minimum of disruption to your existing code and
    without introducing new steps in packaging (e.g. such as compilation of C modules) or necessitating
    a new language (e.g. Cython or C).

    It is up to the user of this library to consider the pros and cons of its use and to test its impact
    on program correctness.

Public API
**********
Please see the :doc:`api_reference`.

Further reading
***************

* codegen-article_ - an article about accelerating Python code using code generation (i.e. the purpose of this package)

Development
***********

For development, we suggest to create a virtual environment and install ``python-dynamic-code`` in
editable mode and ``dev`` dependencies::

    $ python3 -m venv .env
    $ source .env/bin/activate
    $ pip install -e .[dev]

To make sure you follow the code style used in the project, install pre-commit_ which
will run style checks before each commit::

    $ pre-commit install



Table of contents
*****************

.. toctree::
    :maxdepth: 1

    api_reference
    changelog
    todo



.. hyperlinks
.. _self modifying code:
    https://en.wikipedia.org/wiki/Self-modifying_code
.. _tox test suite:
    https://github.com/wahuneke/python-dynamic-code/blob/main/tox.ini
.. _pre-commit:
    https://pre-commit.com/
.. _codegen-article:
    https://medium.com/@yonatanzunger/advanced-python-achieving-high-performance-with-code-generation-796b177ec79
.. _python exec:
    https://docs.python.org/3/library/functions.html#exec

.. Indices and tables
.. ==================
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
