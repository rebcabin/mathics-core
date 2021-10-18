from mathics.core.expression import Expression
from mathics.core.symbols import Symbol, Atom
from mathics.core.atoms import Integer
from mathics.builtin.base import MessageException


def _pspec_span_to_tuple(pspec, expr):
    start = 1
    stop = None
    step = 1
    leaves = pspec.leaves
    if len(leaves) > 3:
        raise MessageException("Part", "span", leaves)
    if len(leaves) > 0:
        start = leaves[0].get_int_value() - 1
    if len(leaves) > 1:
        stop = leaves[1].get_int_value() - 1
    if stop is None:
        if leaves[1].get_name() == "System`All":
            stop = None
        else:
            raise MessageException("Part", "span", pspec)
    if len(pspec.leaves) > 2:
        step = leaves[2].get_int_value()

    if start == 0 or stop == 0:
        # index 0 is undefined
        raise MessageException("Part", "span", 0)
    if start < 0:
        start = len(expr.leaves) - start

    if start is None or step is None:
        raise MessageException("Part", "span", pspec)

    if stop is None:
        stop = 0 if step < 0 else len(expr.leaves) - 1

    if stop < 0:
        stop = len(expr.leaves) - stop

    stop = stop + 1 if step > 0 else stop - 1
    return tuple(k for k in range(start, stop, step))


class ExpressionPointer(object):
    def __init__(self, expr, pos=None, parent=None):
        # If pos is None, and expr is an ExpressionPointer,
        # then just copy it
        if pos is None:
            if type(expr) is ExpressionPointer:
                self.parent = expr.parent
                self.position = expr.position
            else:
                self.parent = expr
                self.position = None
        else:
            if parent:
                self.parent = parent
            else:
                self.parent = expr
            self.position = pos

    def __str__(self) -> str:
        return "%s[[%s]]" % (self.parent, self.position)

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def original(self):
        return None

    @original.setter
    def original(self, value):
        raise ValueError("Expression.original is write protected.")

    @property
    def head(self):
        pos = self.position
        if pos is None:
            return self.parent.head
        elif pos == 0:
            return self.parent.head.head
        return self.parent.leaves[pos - 1].head

    @head.setter
    def head(self, value):
        raise ValueError("ExpressionPointer.head is write protected.")

    @property
    def leaves(self):
        pos = self.position
        if pos is None:
            return self.parent.leaves
        elif pos == 0:
            self.parent.head.leaves
        return self.parent.leaves[pos - 1].leaves

    @leaves.setter
    def leaves(self, value):
        raise ValueError("ExpressionPointer.leaves is write protected.")

    def is_atom(self):
        pos = self.position
        if pos is None:
            return self.parent.is_atom()
        elif pos == 0:
            return self.parent.head.is_atom()
        return self.parent.leaves[pos - 1].is_atom()

    def to_expression(self):
        parent = self.parent
        p = self.position
        if p == 0:
            if type(parent) is Symbol:
                return parent
            else:
                return parent.head.copy()
        else:
            leaf = self.parent.leaves[p - 1]
            if leaf.is_atom():
                return leaf
            else:
                return leaf.copy()

    def replace(self, new):
        parent = self.parent
        while type(parent) is ExpressionPointer:
            position = parent.position
            pos = [self.position]
            if position is None:
                parent = parent.parent
                continue
            pos.append(parent.position)
            parent = parent.parent
        # At this point, we hit the expression, and we have
        # the path to reach the position
        i = pos.pop()
        while pos:
            if i == 0:
                parent = parent._head
            else:
                parent = parent._leaves[i - 1]
            i = pos.pop()

        if i == 0:
            parent.set_head(new)
        else:
            parent.set_leaf(i - 1, new)


class SubExpression(object):
    """
    This class represents a Subexpression of an existing Expression.
    Assignment to a subexpression results in the change of the original Expression.
    """

    def __new__(cls, expr, pos=None):
        """
        `expr` can be an `Expression`, a `ExpressionPointer` or
        another `SubExpression`
        `pos` can be `None`, an integer value or an `Expression` that
        indicates a subset of leaves in the original `Expression`
        """
        # If pos is a list, take the first element
        if type(pos) in (tuple, list):
            pos, rem_pos = pos[0], pos[1:]
            if len(rem_pos) == 0:
                rem_pos = None
        else:
            rem_pos = None

        # Trivial conversion: if pos is an `Integer`, convert
        # to a Python native int
        if type(pos) is Integer:
            pos = pos.get_int_value()
        # pos == `System`All`
        elif type(pos) is Symbol and pos.get_name() == "System`All":
            pos = None
        elif type(pos) is Expression:
            if pos.has_form("System`List", None):
                tuple_pos = [i.get_int_value() for i in pos.leaves]
                if any([i is None for i in tuple_pos]):
                    raise MessageException("Part", "pspec", pos)
                pos = tuple_pos
            elif pos.has_form("System`Span", None):
                pos = _pspec_span_to_tuple(pos, expr)
            else:
                raise MessageException("Part", "pspec", pos)
        if pos is None or type(pos) is int:
            if rem_pos is None:
                return ExpressionPointer(expr, pos)
            else:
                return SubExpression(ExpressionPointer(expr, pos), rem_pos)
        elif type(pos) is tuple:
            self = super(SubExpression, cls).__new__(cls)
            self._headp = ExpressionPointer(expr.head, 0)
            self._leavesp = [
                SubExpression(ExpressionPointer(expr, k + 1), rem_pos) for k in pos
            ]
            return self

    def __str__(self):
        return (
            self.head.__str__()
            + "[\n"
            + ",\n".join(["\t " + leaf.__str__() for leaf in self.leaves])
            + "\n\t]"
        )

    def __repr__(self):
        return self.__str__()

    @property
    def head(self):
        return self._headp

    @head.setter
    def head(self, value):
        raise ValueError("SubExpression.head is write protected.")

    @property
    def leaves(self):
        return self._leavesp

    @leaves.setter
    def leaves(self, value):
        raise ValueError("SubExpression.leaves is write protected.")

    def to_expression(self):
        return Expression(
            self._headp.to_expression(),
            *(leaf.to_expression() for leaf in self._leavesp)
        )
