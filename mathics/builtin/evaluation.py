# -*- coding: utf-8 -*-


from mathics.builtin.base import Predefined, Builtin
from mathics.core.atoms import Integer
from mathics.core.evaluation import MAX_RECURSION_DEPTH, set_python_recursion_limit

from mathics.core.attributes import hold_all, hold_all_complete, protected


class RecursionLimit(Predefined):
    """
    <dl>
    <dt>'$RecursionLimit'
        <dd>specifies the maximum allowable recursion depth after
        which a calculation is terminated.
    </dl>

    Calculations terminated by '$RecursionLimit' return '$Aborted':
    >> a = a + a
     : Recursion depth of 200 exceeded.
     = $Aborted
    >> $RecursionLimit
     = 200

    >> $RecursionLimit = x;
     : Cannot set $RecursionLimit to x; value must be an integer between 20 and 512; use the MATHICS_MAX_RECURSION_DEPTH environment variable to allow higher limits.

    >> $RecursionLimit = 512
     = 512
    >> a = a + a
     : Recursion depth of 512 exceeded.
     = $Aborted

    #> $RecursionLimit = 20
     = 20
    #> a = a + a
     : Recursion depth of 20 exceeded.
     = $Aborted

    #> $RecursionLimit = 200
     = 200

    #> ClearAll[f];
    #> f[x_, 0] := x; f[x_, n_] := f[x + 1, n - 1];
    #> Block[{$RecursionLimit = 20}, f[0, 100]]
     = 100
    #> ClearAll[f];

    #> ClearAll[f];
    #> f[x_, 0] := x; f[x_, n_] := Module[{y = x + 1}, f[y, n - 1]];
    #> Block[{$RecursionLimit = 20}, f[0, 100]]
     : Recursion depth of 20 exceeded.
     = $Aborted
    #> ClearAll[f];
    """

    name = "$RecursionLimit"
    value = 200

    set_python_recursion_limit(value)

    rules = {
        "$RecursionLimit": str(value),
    }

    messages = {
        "reclim": "Recursion depth of `1` exceeded.",
        "limset": (
            "Cannot set $RecursionLimit to `1`; "
            "value must be an integer between 20 and %d; "
            "use the MATHICS_MAX_RECURSION_DEPTH environment variable to allow higher limits."
        )
        % (MAX_RECURSION_DEPTH),
    }

    rules = {
        "$RecursionLimit": str(value),
    }

    def evaluate(self, evaluation) -> Integer:
        return Integer(self.value)


class IterationLimit(Predefined):
    """
    <dl>
        <dt>'$IterationLimit'

        <dd>specifies the maximum number of times a reevaluation of an expression may happen.

    </dl>

    Calculations terminated by '$IterationLimit' return '$Aborted':

    > $IterationLimit
     = 1000
    #> ClearAll[f]; f[x_] := f[x + 1];
    #> f[x]
     : Iteration limit of 1000 exceeded.
     = $Aborted
    #> ClearAll[f];

    #> $IterationLimit = x;
     : Cannot set $IterationLimit to x; value must be an integer between 20 and Infinity.

    #> ClearAll[f];
    #> f[x_, 0] := x; f[x_, n_] := f[x + 1, n - 1];
    #> Block[{$IterationLimit = 20}, f[0, 100]]
     : Iteration limit of 20 exceeded.
     = $Aborted
    #> ClearAll[f];

    # FIX Later
    # #> ClearAll[f];
    # #> f[x_, 0] := x; f[x_, n_] := Module[{y = x + 1}, f[y, n - 1]];
    # #> Block[{$IterationLimit = 20}, f[0, 100]]
    #  = 100
    # #> ClearAll[f];
    """

    name = "$IterationLimit"
    value = 1000

    rules = {
        "$IterationLimit": str(value),
    }

    messages = {
        "itlim": "Iteration limit of `1` exceeded.",
        "limset": (
            "Cannot set $IterationLimit to `1`; "
            "value must be an integer between 20 and Infinity."
        ),
    }

    rules = {
        "$IterationLimit": str(value),
    }

    def evaluate(self, evaluation):
        return Integer(self.value)


class Hold(Builtin):
    """
    <dl>
    <dt>'Hold[$expr$]'
        <dd>prevents $expr$ from being evaluated.
    </dl>
    >> Attributes[Hold]
     = {HoldAll, Protected}
    """

    attributes = hold_all | protected


class HoldComplete(Builtin):
    """
    <dl>
    <dt>'HoldComplete[$expr$]'
        <dd>prevents $expr$ from being evaluated, and also prevents
        'Sequence' objects from being spliced into argument lists.
    </dl>
    >> Attributes[HoldComplete]
     = {HoldAllComplete, Protected}
    """

    attributes = hold_all_complete | protected


class HoldForm(Builtin):
    """
    <dl>
    <dt>'HoldForm[$expr$]'
        <dd>is equivalent to 'Hold[$expr$]', but prints as $expr$.
    </dl>

    >> HoldForm[1 + 2 + 3]
     = 1 + 2 + 3

    'HoldForm' has attribute 'HoldAll':
    >> Attributes[HoldForm]
     = {HoldAll, Protected}
    """

    attributes = hold_all | protected

    rules = {
        "MakeBoxes[HoldForm[expr_], f_]": "MakeBoxes[expr, f]",
    }


class Evaluate(Builtin):
    """
    <dl>
    <dt>'Evaluate[$expr$]'
        <dd>forces evaluation of $expr$, even if it occurs inside a
        held argument or a 'Hold' form.
    </dl>

    Create a function $f$ with a held argument:
    >> SetAttributes[f, HoldAll]
    >> f[1 + 2]
     = f[1 + 2]

    'Evaluate' forces evaluation of the argument, even though $f$ has
    the 'HoldAll' attribute:
    >> f[Evaluate[1 + 2]]
     = f[3]

    >> Hold[Evaluate[1 + 2]]
     = Hold[3]
    >> HoldComplete[Evaluate[1 + 2]]
     = HoldComplete[Evaluate[1 + 2]]
    >> Evaluate[Sequence[1, 2]]
     = Sequence[1, 2]
    """

    rules = {
        "Evaluate[Unevaluated[x_]]": "Unevaluated[x]",
        "Evaluate[x___]": "x",
    }


class Unevaluated(Builtin):
    """
    <dl>
    <dt>'Unevaluated[$expr$]'
        <dd>temporarily leaves $expr$ in an unevaluated form when it
        appears as a function argument.
    </dl>

    'Unevaluated' is automatically removed when function arguments are
    evaluated:
    >> Sqrt[Unevaluated[x]]
     = Sqrt[x]

    >> Length[Unevaluated[1+2+3+4]]
     = 4
    'Unevaluated' has attribute 'HoldAllComplete':
    >> Attributes[Unevaluated]
     = {HoldAllComplete, Protected}

    'Unevaluated' is maintained for arguments to non-executed functions:
    >> f[Unevaluated[x]]
     = f[Unevaluated[x]]
    Likewise, its kept in flattened arguments and sequences:
    >> Attributes[f] = {Flat};
    >> f[a, Unevaluated[f[b, c]]]
     = f[a, Unevaluated[b], Unevaluated[c]]
    >> g[a, Sequence[Unevaluated[b], Unevaluated[c]]]
     = g[a, Unevaluated[b], Unevaluated[c]]
    However, unevaluated sequences are kept:
    >> g[Unevaluated[Sequence[a, b, c]]]
     = g[Unevaluated[Sequence[a, b, c]]]

    #> Attributes[h] = Flat;
    #> h[items___] := Plus[items]
    #> h[1, Unevaluated[Sequence[Unevaluated[2], 3]], Sequence[4, Unevaluated[5]]]
     = 15
    """

    attributes = hold_all_complete | protected


class ReleaseHold(Builtin):
    """
    <dl>
    <dt>'ReleaseHold[$expr$]'
        <dd>removes any 'Hold', 'HoldForm', 'HoldPattern' or
        'HoldComplete' head from $expr$.
    </dl>
    >> x = 3;
    >> Hold[x]
     = Hold[x]
    >> ReleaseHold[Hold[x]]
     = 3
    >> ReleaseHold[y]
     = y
    """

    rules = {
        "ReleaseHold[(Hold|HoldForm|HoldPattern|HoldComplete)[expr_]]": "expr",
        "ReleaseHold[other_]": "other",
    }


class Sequence(Builtin):
    """
    <dl>
    <dt>'Sequence[$x1$, $x2$, ...]'
        <dd>represents a sequence of arguments to a function.
    </dl>

    'Sequence' is automatically spliced in, except when a function has attribute 'SequenceHold'
    (like assignment functions).
    >> f[x, Sequence[a, b], y]
     = f[x, a, b, y]
    >> Attributes[Set]
     = {HoldFirst, Protected, SequenceHold}
    >> a = Sequence[b, c];
    >> a
     = Sequence[b, c]

    Apply 'Sequence' to a list to splice in arguments:
    >> list = {1, 2, 3};
    >> f[Sequence @@ list]
     = f[1, 2, 3]

    Inside 'Hold' or a function with a held argument, 'Sequence' is
    spliced in at the first level of the argument:
    >> Hold[a, Sequence[b, c], d]
     = Hold[a, b, c, d]
    If 'Sequence' appears at a deeper level, it is left unevaluated:
    >> Hold[{a, Sequence[b, c], d}]
     = Hold[{a, Sequence[b, c], d}]
    """


class Quit(Builtin):
    """
    <dl>
    <dt>'Quit'[]
      <dd> Terminates the Mathics session.
    <dt>'Quit[$n$]'
      <dd> Terminates the mathics session with exit code $n$.
    </dl>

    <dl>
    <dt>'Exit'[]
      <dd> Terminates the Mathics session.
    <dt>'Exit[$n$]'
      <dd> Terminates the mathics session with exit code $n$.
    </dl>

    """

    rules = {
        "Exit[n___]": "Quit[n]",
    }

    def apply(self, evaluation, n):
        "%(name)s[n___]"
        exitcode = 0
        if isinstance(n, Integer):
            exitcode = n.get_int_value()
        raise SystemExit(exitcode)
