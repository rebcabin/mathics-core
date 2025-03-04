# -*- coding: utf-8 -*-


from mathics.algorithm.parts import walk_parts
from mathics.core.evaluation import MAX_RECURSION_DEPTH, set_python_recursion_limit
from mathics.core.expression import Expression
from mathics.core.rules import Rule
from mathics.core.symbols import (
    Symbol,
    SymbolN,
    system_symbols,
    valid_context_name,
)
from mathics.core.systemsymbols import SymbolMachinePrecision

from mathics.core.attributes import attribute_string_to_number, locked, protected

from functools import reduce


class AssignmentException(Exception):
    def __init__(self, lhs, rhs) -> None:
        super().__init__(" %s cannot be assigned to %s" % (rhs, lhs))
        self.lhs = lhs
        self.rhs = rhs


def assign_store_rules_by_tag(self, lhs, rhs, evaluation, tags, upset=None):
    lhs, condition = unroll_conditions(lhs)
    lhs, rhs = unroll_patterns(lhs, rhs, evaluation)
    count = 0
    defs = evaluation.definitions
    ignore_protection, tags = process_assign_other(
        self, lhs, rhs, evaluation, tags, upset
    )
    lhs, rhs = process_rhs_conditions(lhs, rhs, condition, evaluation)
    count = 0
    rule = Rule(lhs, rhs)
    position = "up" if upset else None
    for tag in tags:
        if rejected_because_protected(self, lhs, tag, evaluation, ignore_protection):
            continue
        count += 1
        defs.add_rule(tag, rule, position=position)
    return count > 0


def build_rulopc(optval):
    return Rule(
        Expression(
            "OptionValue",
            Expression("Pattern", Symbol("$cond$"), Expression("Blank")),
        ),
        Expression("OptionValue", optval, Symbol("$cond$")),
    )


def get_symbol_list(list, error_callback):
    if list.has_form("List", None):
        list = list.leaves
    else:
        list = [list]
    values = []
    for item in list:
        name = item.get_name()
        if name:
            values.append(name)
        else:
            error_callback(item)
            return None
    return values


def get_symbol_values(symbol, func_name, position, evaluation):
    name = symbol.get_name()
    if not name:
        evaluation.message(func_name, "sym", symbol, 1)
        return
    if position in ("default",):
        definition = evaluation.definitions.get_definition(name)
    else:
        definition = evaluation.definitions.get_user_definition(name)
    leaves = []
    for rule in definition.get_values_list(position):
        if isinstance(rule, Rule):
            pattern = rule.pattern
            if pattern.has_form("HoldPattern", 1):
                pattern = pattern.expr
            else:
                pattern = Expression("HoldPattern", pattern.expr)
            leaves.append(Expression("RuleDelayed", pattern, rule.replace))
    return Expression("List", *leaves)


def is_protected(tag, defin):
    return protected & defin.get_attributes(tag)


def repl_pattern_by_symbol(expr):
    leaves = expr.get_leaves()
    if len(leaves) == 0:
        return expr

    headname = expr.get_head_name()
    if headname == "System`Pattern":
        return leaves[0]

    changed = False
    newleaves = []
    for leave in leaves:
        leaf = repl_pattern_by_symbol(leave)
        if not (leaf is leave):
            changed = True
        newleaves.append(leaf)
    if changed:
        return Expression(headname, *newleaves)
    else:
        return expr


# Here are the functions related to assign_elementary

# Auxiliary routines


def rejected_because_protected(self, lhs, tag, evaluation, ignore=False):
    defs = evaluation.definitions
    if not ignore and is_protected(tag, defs):
        if lhs.get_name() == tag:
            evaluation.message(self.get_name(), "wrsym", Symbol(tag))
        else:
            evaluation.message(self.get_name(), "write", Symbol(tag), lhs)
        return True
    return False


def find_tag_and_check(lhs, tags, evaluation):
    name = lhs.get_head_name()
    if len(lhs.leaves) != 1:
        evaluation.message_args(name, len(lhs.leaves), 1)
        raise AssignmentException(lhs, None)
    tag = lhs.leaves[0].get_name()
    if not tag:
        evaluation.message(name, "sym", lhs.leaves[0], 1)
        raise AssignmentException(lhs, None)
    if tags is not None and tags != [tag]:
        evaluation.message(name, "tag", Symbol(name), Symbol(tag))
        raise AssignmentException(lhs, None)
    if is_protected(tag, evaluation.definitions):
        evaluation.message(name, "wrsym", Symbol(tag))
        raise AssignmentException(lhs, None)
    return tag


def unroll_patterns(lhs, rhs, evaluation):
    if type(lhs) is Symbol:
        return lhs, rhs
    name = lhs.get_head_name()
    lhsleaves = lhs._leaves
    if name == "System`Pattern":
        lhs = lhsleaves[1]
        rulerepl = (lhsleaves[0], repl_pattern_by_symbol(lhs))
        rhs, status = rhs.apply_rules([Rule(*rulerepl)], evaluation)
        name = lhs.get_head_name()

    if name == "System`HoldPattern":
        lhs = lhsleaves[0]
        name = lhs.get_head_name()
    return lhs, rhs


def unroll_conditions(lhs):
    condition = None
    if type(lhs) is Symbol:
        return lhs, None
    else:
        name, lhs_leaves = lhs.get_head_name(), lhs._leaves
    condition = []
    # This handle the case of many sucesive conditions:
    # f[x_]/; cond1 /; cond2 ... ->  f[x_]/; And[cond1, cond2, ...]
    while name == "System`Condition" and len(lhs.leaves) == 2:
        condition.append(lhs_leaves[1])
        lhs = lhs_leaves[0]
        name, lhs_leaves = lhs.get_head_name(), lhs._leaves
    if len(condition) == 0:
        return lhs, None
    if len(condition) > 1:
        condition = Expression("System`And", *condition)
    else:
        condition = condition[0]
    condition = Expression("System`Condition", lhs, condition)
    lhs._format_cache = None
    return lhs, condition


# Here starts the functions that implement `assign_elementary` for different
# kind of expressions. Maybe they should be put in a separated module or
# maybe they should be member functions of _SetOperator.


def process_assign_recursion_limit(lhs, rhs, evaluation):
    rhs_int_value = rhs.get_int_value()
    # if (not rhs_int_value or rhs_int_value < 20) and not
    # rhs.get_name() == 'System`Infinity':
    if (
        not rhs_int_value or rhs_int_value < 20 or rhs_int_value > MAX_RECURSION_DEPTH
    ):  # nopep8

        evaluation.message("$RecursionLimit", "limset", rhs)
        raise AssignmentException(lhs, None)
    try:
        set_python_recursion_limit(rhs_int_value)
    except OverflowError:
        # TODO: Message
        raise AssignmentException(lhs, None)
    return False


def process_assign_iteration_limit(lhs, rhs, evaluation):
    rhs_int_value = rhs.get_int_value()
    if (
        not rhs_int_value or rhs_int_value < 20
    ) and not rhs.get_name() == "System`Infinity":
        evaluation.message("$IterationLimit", "limset", rhs)
        raise AssignmentException(lhs, None)
    return False


def process_assign_module_number(lhs, rhs, evaluation):
    rhs_int_value = rhs.get_int_value()
    if not rhs_int_value or rhs_int_value <= 0:
        evaluation.message("$ModuleNumber", "set", rhs)
        raise AssignmentException(lhs, None)
    return False


def process_assign_line_number_and_history_length(
    self, lhs, rhs, evaluation, tags, upset
):
    lhs_name = lhs.get_name()
    rhs_int_value = rhs.get_int_value()
    if rhs_int_value is None or rhs_int_value < 0:
        evaluation.message(lhs_name, "intnn", rhs)
        raise AssignmentException(lhs, None)
    return False


def process_assign_random_state(self, lhs, rhs, evaluation, tags, upset):
    # TODO: allow setting of legal random states!
    # (but consider pickle's insecurity!)
    evaluation.message("$RandomState", "rndst", rhs)
    raise AssignmentException(lhs, None)


def process_assign_context(self, lhs, rhs, evaluation, tags, upset):
    lhs_name = lhs.get_head_name()
    new_context = rhs.get_string_value()
    if new_context is None or not valid_context_name(
        new_context, allow_initial_backquote=True
    ):
        evaluation.message(lhs_name, "cxset", rhs)
        raise AssignmentException(lhs, None)

    # With $Context in Mathematica you can do some strange
    # things: e.g. with $Context set to Global`, something
    # like:
    #    $Context = "`test`"; newsym
    # is accepted and creates Global`test`newsym.
    # Implement this behaviour by interpreting
    #    $Context = "`test`"
    # as
    #    $Context = $Context <> "test`"
    #
    if new_context.startswith("`"):
        new_context = evaluation.definitions.get_current_context() + new_context.lstrip(
            "`"
        )

    evaluation.definitions.set_current_context(new_context)
    return True


def process_assign_context_path(self, lhs, rhs, evaluation, tags, upset):
    lhs_name = lhs.get_name()
    currContext = evaluation.definitions.get_current_context()
    context_path = [s.get_string_value() for s in rhs.get_leaves()]
    context_path = [
        s if (s is None or s[0] != "`") else currContext[:-1] + s for s in context_path
    ]
    if rhs.has_form("List", None) and all(valid_context_name(s) for s in context_path):
        evaluation.definitions.set_context_path(context_path)
        return True
    else:
        evaluation.message(lhs_name, "cxlist", rhs)
        raise AssignmentException(lhs, None)


def process_assign_minprecision(self, lhs, rhs, evaluation, tags, upset):
    lhs_name = lhs.get_name()
    rhs_int_value = rhs.get_int_value()
    # $MinPrecision = Infinity is not allowed
    if rhs_int_value is not None and rhs_int_value >= 0:
        max_prec = evaluation.definitions.get_config_value("$MaxPrecision")
        if max_prec is not None and max_prec < rhs_int_value:
            evaluation.message("$MinPrecision", "preccon", Symbol("$MinPrecision"))
            raise AssignmentException(lhs, None)
        return False
    else:
        evaluation.message(lhs_name, "precset", lhs, rhs)
        raise AssignmentException(lhs, None)


def process_assign_maxprecision(self, lhs, rhs, evaluation, tags, upset):
    lhs_name = lhs.get_name()
    rhs_int_value = rhs.get_int_value()
    if rhs.has_form("DirectedInfinity", 1) and rhs.leaves[0].get_int_value() == 1:
        return False
    elif rhs_int_value is not None and rhs_int_value > 0:
        min_prec = evaluation.definitions.get_config_value("$MinPrecision")
        if min_prec is not None and rhs_int_value < min_prec:
            evaluation.message("$MaxPrecision", "preccon", Symbol("$MaxPrecision"))
            raise AssignmentException(lhs, None)
        return False
    else:
        evaluation.message(lhs_name, "precset", lhs, rhs)
        raise AssignmentException(lhs, None)


def process_assign_definition_values(self, lhs, rhs, evaluation, tags, upset):
    name = lhs.get_head_name()
    tag = find_tag_and_check(lhs, tags, evaluation)
    rules = rhs.get_rules_list()
    if rules is None:
        evaluation.message(name, "vrule", lhs, rhs)
        raise AssignmentException(lhs, None)
    evaluation.definitions.set_values(tag, name, rules)
    return True


def process_assign_options(self, lhs, rhs, evaluation, tags, upset):
    lhs_leaves = lhs.leaves
    name = lhs.get_head_name()
    if len(lhs_leaves) != 1:
        evaluation.message_args(name, len(lhs_leaves), 1)
        raise AssignmentException(lhs, rhs)
    tag = lhs_leaves[0].get_name()
    if not tag:
        evaluation.message(name, "sym", lhs_leaves[0], 1)
        raise AssignmentException(lhs, rhs)
    if tags is not None and tags != [tag]:
        evaluation.message(name, "tag", Symbol(name), Symbol(tag))
        raise AssignmentException(lhs, rhs)
    if is_protected(tag, evaluation.definitions):
        evaluation.message(name, "wrsym", Symbol(tag))
        raise AssignmentException(lhs, None)
    option_values = rhs.get_option_values(evaluation)
    if option_values is None:
        evaluation.message(name, "options", rhs)
        raise AssignmentException(lhs, None)
    evaluation.definitions.set_options(tag, option_values)
    return True


def process_assign_n(self, lhs, rhs, evaluation, tags, upset):
    lhs, condition = unroll_conditions(lhs)
    lhs, rhs = unroll_patterns(lhs, rhs, evaluation)
    defs = evaluation.definitions

    if len(lhs.leaves) not in (1, 2):
        evaluation.message_args("N", len(lhs.leaves), 1, 2)
        raise AssignmentException(lhs, None)
    if len(lhs.leaves) == 1:
        nprec = SymbolMachinePrecision
    else:
        nprec = lhs.leaves[1]
    focus = lhs.leaves[0]
    lhs = Expression(SymbolN, focus, nprec)
    tags = process_tags_and_upset_dont_allow_custom(
        tags, upset, self, lhs, focus, evaluation
    )
    count = 0
    lhs, rhs = process_rhs_conditions(lhs, rhs, condition, evaluation)
    rule = Rule(lhs, rhs)
    for tag in tags:
        if rejected_because_protected(self, lhs, tag, evaluation):
            continue
        count += 1
        defs.add_nvalue(tag, rule)
    return count > 0


def process_assign_other(self, lhs, rhs, evaluation, tags=None, upset=False):
    tags, focus = process_tags_and_upset_allow_custom(
        tags, upset, self, lhs, evaluation
    )
    lhs_name = lhs.get_name()
    if lhs_name == "System`$RecursionLimit":
        process_assign_recursion_limit(self, lhs, rhs, evaluation, tags, upset)
    elif lhs_name in ("System`$Line", "System`$HistoryLength"):
        process_assign_line_number_and_history_length(
            self, lhs, rhs, evaluation, tags, upset
        )
    elif lhs_name == "System`$IterationLimit":
        process_assign_iteration_limit(self, lhs, rhs, evaluation, tags, upset)
    elif lhs_name == "System`$ModuleNumber":
        process_assign_module_number(self, lhs, rhs, evaluation, tags, upset)
    elif lhs_name == "System`$MinPrecision":
        process_assign_minprecision(self, lhs, rhs, evaluation, tags, upset)
    elif lhs_name == "System`$MaxPrecision":
        process_assign_maxprecision(self, lhs, rhs, evaluation, tags, upset)
    else:
        return False, tags
    return True, tags


def process_assign_attributes(self, lhs, rhs, evaluation, tags, upset):
    name = lhs.get_head_name()
    if len(lhs.leaves) != 1:
        evaluation.message_args(name, len(lhs.leaves), 1)
        raise AssignmentException(lhs, rhs)
    tag = lhs.leaves[0].get_name()
    if not tag:
        evaluation.message(name, "sym", lhs.leaves[0], 1)
        raise AssignmentException(lhs, rhs)
    if tags is not None and tags != [tag]:
        evaluation.message(name, "tag", Symbol(name), Symbol(tag))
        raise AssignmentException(lhs, rhs)
    attributes_list = get_symbol_list(
        rhs, lambda item: evaluation.message(name, "sym", item, 1)
    )
    if attributes_list is None:
        raise AssignmentException(lhs, rhs)
    if locked & evaluation.definitions.get_attributes(tag):
        evaluation.message(name, "locked", Symbol(tag))
        raise AssignmentException(lhs, rhs)

    def reduce_attributes_from_list(x: int, y: str) -> int:
        try:
            return x | attribute_string_to_number[y]
        except KeyError:
            evaluation.message("SetAttributes", "unknowattr", y)
            return x

    attributes = reduce(
        reduce_attributes_from_list,
        attributes_list,
        0,
    )

    evaluation.definitions.set_attributes(tag, attributes)

    return True


def process_assign_default(self, lhs, rhs, evaluation, tags, upset):
    lhs, condition = unroll_conditions(lhs)
    lhs, rhs = unroll_patterns(lhs, rhs, evaluation)
    count = 0
    defs = evaluation.definitions

    if len(lhs.leaves) not in (1, 2, 3):
        evaluation.message_args("Default", len(lhs.leaves), 1, 2, 3)
        raise AssignmentException(lhs, None)
    focus = lhs.leaves[0]
    tags = process_tags_and_upset_dont_allow_custom(
        tags, upset, self, lhs, focus, evaluation
    )
    lhs, rhs = process_rhs_conditions(lhs, rhs, condition, evaluation)
    rule = Rule(lhs, rhs)
    for tag in tags:
        if rejected_because_protected(self, lhs, tag, evaluation):
            continue
        count += 1
        defs.add_default(tag, rule)
    return count > 0


def process_assign_format(self, lhs, rhs, evaluation, tags, upset):
    lhs, condition = unroll_conditions(lhs)
    lhs, rhs = unroll_patterns(lhs, rhs, evaluation)
    count = 0
    defs = evaluation.definitions

    if len(lhs.leaves) not in (1, 2):
        evaluation.message_args("Format", len(lhs.leaves), 1, 2)
        raise AssignmentException(lhs, None)
    if len(lhs.leaves) == 2:
        form = lhs.leaves[1].get_name()
        if not form:
            evaluation.message("Format", "fttp", lhs.leaves[1])
            raise AssignmentException(lhs, None)
    else:
        form = system_symbols(
            "StandardForm",
            "TraditionalForm",
            "OutputForm",
            "TeXForm",
            "MathMLForm",
        )
        form = [f.name for f in form]
    lhs = focus = lhs.leaves[0]
    tags = process_tags_and_upset_dont_allow_custom(
        tags, upset, self, lhs, focus, evaluation
    )
    lhs, rhs = process_rhs_conditions(lhs, rhs, condition, evaluation)
    rule = Rule(lhs, rhs)
    for tag in tags:
        if rejected_because_protected(self, lhs, tag, evaluation):
            continue
        count += 1
        defs.add_format(tag, rule, form)
    return count > 0


def process_assign_messagename(self, lhs, rhs, evaluation, tags, upset):
    lhs, condition = unroll_conditions(lhs)
    lhs, rhs = unroll_patterns(lhs, rhs, evaluation)
    count = 0
    defs = evaluation.definitions
    if len(lhs.leaves) != 2:
        evaluation.message_args("MessageName", len(lhs.leaves), 2)
        raise AssignmentException(lhs, None)
    focus = lhs.leaves[0]
    tags = process_tags_and_upset_dont_allow_custom(
        tags, upset, self, lhs, focus, evaluation
    )
    lhs, rhs = process_rhs_conditions(lhs, rhs, condition, evaluation)
    rule = Rule(lhs, rhs)
    for tag in tags:
        if rejected_because_protected(self, lhs, tag, evaluation):
            continue
        count += 1
        defs.add_message(tag, rule)
    return count > 0


def process_rhs_conditions(lhs, rhs, condition, evaluation):
    # To Handle `OptionValue` in `Condition`
    rulopc = build_rulopc(lhs.get_head())
    rhs_name = rhs.get_head_name()
    while rhs_name == "System`Condition":
        if len(rhs.leaves) != 2:
            evaluation.message_args("Condition", len(rhs.leaves), 2)
            raise AssignmentException(lhs, None)
        lhs = Expression(
            "Condition", lhs, rhs.leaves[1].apply_rules([rulopc], evaluation)[0]
        )
        rhs = rhs.leaves[0]
        rhs_name = rhs.get_head_name()

    # Now, let's add the conditions on the LHS
    if condition:
        lhs = Expression(
            "Condition",
            lhs,
            condition.leaves[1].apply_rules([rulopc], evaluation)[0],
        )
    return lhs, rhs


def process_tags_and_upset_dont_allow_custom(tags, upset, self, lhs, focus, evaluation):
    # TODO: the following provides a hacky fix for 1259. I know @rocky loves
    # this kind of things, but otherwise we need to work on rebuild the pattern
    # matching mechanism...
    flag_ioi, evaluation.ignore_oneidentity = evaluation.ignore_oneidentity, True
    focus = focus.evaluate_leaves(evaluation)
    evaluation.ignore_oneidentity = flag_ioi
    name = lhs.get_head_name()
    if tags is None and not upset:
        name = focus.get_lookup_name()
        if not name:
            evaluation.message(self.get_name(), "setraw", focus)
            raise AssignmentException(lhs, None)
        tags = [name]
    elif upset:
        tags = [focus.get_lookup_name()]
    else:
        allowed_names = [focus.get_lookup_name()]
        for name in tags:
            if name not in allowed_names:
                evaluation.message(self.get_name(), "tagnfd", Symbol(name))
                raise AssignmentException(lhs, None)
    return tags


def process_tags_and_upset_allow_custom(tags, upset, self, lhs, evaluation):
    # TODO: the following provides a hacky fix for 1259. I know @rocky loves
    # this kind of things, but otherwise we need to work on rebuild the pattern
    # matching mechanism...
    name = lhs.get_head_name()
    focus = lhs
    flag_ioi, evaluation.ignore_oneidentity = evaluation.ignore_oneidentity, True
    focus = focus.evaluate_leaves(evaluation)
    evaluation.ignore_oneidentity = flag_ioi
    if tags is None and not upset:
        name = focus.get_lookup_name()
        if not name:
            evaluation.message(self.get_name(), "setraw", focus)
            raise AssignmentException(lhs, None)
        tags = [name]
    elif upset:
        tags = []
        if focus.is_atom():
            evaluation.message(self.get_name(), "normal")
            raise AssignmentException(lhs, None)
        for leaf in focus.leaves:
            name = leaf.get_lookup_name()
            tags.append(name)
    else:
        allowed_names = [focus.get_lookup_name()]
        for leaf in focus.get_leaves():
            if not leaf.is_symbol() and leaf.get_head_name() in ("System`HoldPattern",):
                leaf = leaf.leaves[0]
            if not leaf.is_symbol() and leaf.get_head_name() in ("System`Pattern",):
                leaf = leaf.leaves[1]
            if not leaf.is_symbol() and leaf.get_head_name() in (
                "System`Blank",
                "System`BlankSequence",
                "System`BlankNullSequence",
            ):
                if len(leaf.leaves) == 1:
                    leaf = leaf.leaves[0]

            allowed_names.append(leaf.get_lookup_name())
        for name in tags:
            if name not in allowed_names:
                evaluation.message(self.get_name(), "tagnfd", Symbol(name))
                raise AssignmentException(lhs, None)

    return tags, focus


class _SetOperator(object):
    special_cases = {
        "System`OwnValues": process_assign_definition_values,
        "System`DownValues": process_assign_definition_values,
        "System`SubValues": process_assign_definition_values,
        "System`UpValues": process_assign_definition_values,
        "System`NValues": process_assign_definition_values,
        "System`DefaultValues": process_assign_definition_values,
        "System`Messages": process_assign_definition_values,
        "System`Attributes": process_assign_attributes,
        "System`Options": process_assign_options,
        "System`$RandomState": process_assign_random_state,
        "System`$Context": process_assign_context,
        "System`$ContextPath": process_assign_context_path,
        "System`N": process_assign_n,
        "System`MessageName": process_assign_messagename,
        "System`Default": process_assign_default,
        "System`Format": process_assign_format,
    }

    def assign_elementary(self, lhs, rhs, evaluation, tags=None, upset=False):
        if type(lhs) is Symbol:
            name = lhs.name
        else:
            name = lhs.get_head_name()
        lhs._format_cache = None
        try:
            # Deal with direct assignation to properties of
            # the definition object
            func = self.special_cases.get(name, None)
            if func:
                return func(self, lhs, rhs, evaluation, tags, upset)

            return assign_store_rules_by_tag(self, lhs, rhs, evaluation, tags, upset)
        except AssignmentException:
            return False

    def assign(self, lhs, rhs, evaluation):
        lhs._format_cache = None
        defs = evaluation.definitions
        if lhs.get_head_name() == "System`List":
            if not (rhs.get_head_name() == "System`List") or len(lhs.leaves) != len(
                rhs.leaves
            ):  # nopep8

                evaluation.message(self.get_name(), "shape", lhs, rhs)
                return False
            else:
                result = True
                for left, right in zip(lhs.leaves, rhs.leaves):
                    if not self.assign(left, right, evaluation):
                        result = False
                return result
        elif lhs.get_head_name() == "System`Part":
            if len(lhs.leaves) < 1:
                evaluation.message(self.get_name(), "setp", lhs)
                return False
            symbol = lhs.leaves[0]
            name = symbol.get_name()
            if not name:
                evaluation.message(self.get_name(), "setps", symbol)
                return False
            if is_protected(name, defs):
                evaluation.message(self.get_name(), "wrsym", symbol)
                return False
            rule = defs.get_ownvalue(name)
            if rule is None:
                evaluation.message(self.get_name(), "noval", symbol)
                return False
            indices = lhs.leaves[1:]
            return walk_parts([rule.replace], indices, evaluation, rhs)
        else:
            return self.assign_elementary(lhs, rhs, evaluation)
