# cython: language_level=3
# -*- coding: utf-8 -*-

from mathics.core.symbols import (
    Symbol,
    SymbolList,
    SymbolMakeBoxes,
    SymbolTrue,
    SymbolFalse,
    SymbolN,
    SymbolNull,
)

# Some other common Symbols. This list is sorted in alpabetic order.
SymbolAborted = Symbol("$Aborted")
SymbolAssociation = Symbol("Association")
SymbolByteArray = Symbol("ByteArray")
SymbolComplexInfinity = Symbol("ComplexInfinity")
SymbolDirectedInfinity = Symbol("DirectedInfinity")
SymbolFailed = Symbol("$Failed")
SymbolGreater = Symbol("Greater")
SymbolI = Symbol("I")
SymbolInfinity = Symbol("Infinity")
SymbolLess = Symbol("Less")
SymbolMachinePrecision = Symbol("MachinePrecision")
SymbolPower = Symbol("Power")
SymbolPlus = Symbol("Plus")
SymbolRule = Symbol("Rule")
SymbolSequence = Symbol("Sequence")
SymbolTimes = Symbol("Times")
SymbolUndefined = Symbol("Undefined")
