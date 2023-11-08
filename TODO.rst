Wishlist, areas for investigation, possible improvements, etc:

* consider a configurable restriction of the global namespace
* investigate options for identifying high risk injections (i.e. strings)
* is there a significant cost to calling 'globals()' and/or 'locals()'? could we pre-calculate these
  values and then pass in a fixed global or even a fixed local namespace in order to get faster ``exec``?
* rewrite the Runner and Builder code in fast C
* improve handling for fast path funcs that have other decorators on them. Right now, the func is read directly as a
  container for source code and any attached decorators are lost / meaningless
* fix (finish implement) support for attaching to staticmethod and classmethod fast path functions (instead of current
  limit of only attaching to standalone functions and to regular methods)
