Architecture and High Level Design
===================================

The architecture of the system is based on the following components:

* **a decorated function** - the source code inside a function will be annotated with PDC Directives and will
  be decorated with an instance of DynamicCodeBuilder

  - At runtime, accessing the decorated function (or instance method, or classmethod) will provide access to an instance
    of DynamicCodeRunner.  The primary usage of which is to be callable and to proxy calls through a pipeline of
    re-written code

* **a DynamicCodeBuilder** - implemented by the user of the ``PDC`` package, the builder allows for customization of
  behavior

* **code transformation** - based on annotations in the source code of the decorated function, the original source code
  go through two stages of transformation:

  - **conversion code** - the source code is transformed (at program load time) into conversion code which can be run
    whenever needed to provide *exec code*

  - **exec code** - this code is ultimately what is executed when the decorated function is called. It is dynamically
    built (and optionally, automatically rebuilt) based on a subset of function call arguments

* **code execution** - traditionally, Python programs execute code which was read from a Python source file (a module)
  and this determines the scope of names the running code will have access to (e.g. imports, globals defined, other
  functions defined in the module, etc).  In ``PDC`` we have to take steps to run the new code in the same scope as the
  source code it was generated from

  - **debugger integration** - code execution is also the domain area where the package attempts to interact
    sensibly with the Python debugger and with the traceback system.  Ideally, it should be possible to set breakpoints
    in the original source code and have them work as expected when the code is re-written

    This ability is currently a "stretch goal" and is not yet implemented

* **code annotation** - the package provides a language of directives which are intended to allow for useful
  transformations of the original source code.  These directives generally will act in two areas:

  1. Cause source code statements and blocks to be copied "verbatim" into conversion code and / or exec code
  2. Provide for the creation of brand new code and code **replacement** in order to allow for the creation of
     precalculated values

Component Implementation Overviews
===================================
