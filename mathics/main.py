#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import locale
import os
import re
import subprocess
import sys

import os.path as osp

from mathics import settings
from mathics import version_string, license_string, __version__
from mathics.builtin.trace import TraceBuiltins, traced_do_replace
from mathics.core.definitions import autoload_files, Definitions, Symbol
from mathics.core.evaluation import Evaluation, Output
from mathics.core.expression import strip_context
from mathics.core.parser import MathicsFileLineFeeder, MathicsLineFeeder
from mathics.core.rules import BuiltinRule


def get_srcdir():
    filename = osp.normcase(osp.dirname(osp.abspath(__file__)))
    return osp.realpath(filename)


class TerminalShell(MathicsLineFeeder):
    def __init__(self, definitions, colors, want_readline, want_completion):
        super(TerminalShell, self).__init__("<stdin>")
        self.input_encoding = locale.getpreferredencoding()
        self.lineno = 0

        # Try importing readline to enable arrow keys support etc.
        self.using_readline = False
        try:
            if want_readline:
                import readline

                self.using_readline = sys.stdin.isatty() and sys.stdout.isatty()
                self.ansi_color_re = re.compile("\033\\[[0-9;]+m")
                if want_completion:
                    readline.set_completer(
                        lambda text, state: self.complete_symbol_name(text, state)
                    )

                    # Make _ a delimiter, but not $ or `
                    readline.set_completer_delims(
                        " \t\n_~!@#%^&*()-=+[{]}\\|;:'\",<>/?"
                    )

                    readline.parse_and_bind("tab: complete")
                    self.completion_candidates = []
        except ImportError:
            pass

        # Try importing colorama to escape ansi sequences for cross platform
        # colors
        try:
            from colorama import init as colorama_init
        except ImportError:
            colors = "NoColor"
        else:
            colorama_init()
            if colors is None:
                terminal_supports_color = (
                    sys.stdout.isatty() and os.getenv("TERM") != "dumb"
                )
                colors = "Linux" if terminal_supports_color else "NoColor"

        color_schemes = {
            "NOCOLOR": (["", "", "", ""], ["", "", "", ""]),
            "NONE": (["", "", "", ""], ["", "", "", ""]),
            "LINUX": (
                ["\033[32m", "\033[1m", "\033[0m\033[32m", "\033[39m"],
                ["\033[31m", "\033[1m", "\033[0m\033[32m", "\033[39m"],
            ),
            "LIGHTBG": (
                ["\033[34m", "\033[1m", "\033[22m", "\033[39m"],
                ["\033[31m", "\033[1m", "\033[22m", "\033[39m"],
            ),
        }

        # Handle any case by using .upper()
        term_colors = color_schemes.get(colors.upper())
        if term_colors is None:
            out_msg = "The 'colors' argument must be {0} or None"
            print(out_msg.format(repr(list(color_schemes.keys()))))
            quit()

        self.incolors, self.outcolors = term_colors
        self.definitions = definitions
        autoload_files(definitions, get_srcdir(), "autoload-cli")

    def get_last_line_number(self):
        return self.definitions.get_line_no()

    def get_in_prompt(self):
        next_line_number = self.get_last_line_number() + 1
        if self.lineno > 0:
            return " " * len("In[{0}]:= ".format(next_line_number))
        else:
            return "{1}In[{2}{0}{3}]:= {4}".format(next_line_number, *self.incolors)

    def get_out_prompt(self):
        line_number = self.get_last_line_number()
        return "{1}Out[{2}{0}{3}]= {4}".format(line_number, *self.outcolors)

    def to_output(self, text):
        line_number = self.get_last_line_number()
        newline = "\n" + " " * len("Out[{0}]= ".format(line_number))
        return newline.join(text.splitlines())

    def out_callback(self, out):
        print(self.to_output(str(out)))

    def read_line(self, prompt):
        if self.using_readline:
            return self.rl_read_line(prompt)
        return input(prompt)

    def print_result(self, result, no_out_prompt=False, strict_wl_output=False):
        if result is None:
            # FIXME decide what to do here
            return

        last_eval = result.last_eval

        eval_type = None
        if last_eval is not None:
            try:
                eval_type = last_eval.get_head_name()
            except:
                print(sys.exc_info()[1])
                return

        out_str = str(result.result)
        if eval_type == "System`String" and not strict_wl_output:
            out_str = '"' + out_str.replace('"', r"\"") + '"'
        if eval_type == "System`Graph":
            out_str = "-Graph-"

        output = self.to_output(out_str)
        mess = self.get_out_prompt() if not no_out_prompt else ""
        print(mess + output + "\n")

    def rl_read_line(self, prompt):
        # Wrap ANSI colour sequences in \001 and \002, so readline
        # knows that they're nonprinting.
        prompt = self.ansi_color_re.sub(lambda m: "\001" + m.group(0) + "\002", prompt)

        return input(prompt)

    def complete_symbol_name(self, text, state):
        try:
            return self._complete_symbol_name(text, state)
        except Exception:
            # any exception thrown inside the completer gets silently
            # thrown away otherwise
            print("Unhandled error in readline completion")

    def _complete_symbol_name(self, text, state):
        # The readline module calls this function repeatedly,
        # increasing 'state' each time and expecting one string to be
        # returned per call.

        if state == 0:
            self.completion_candidates = self.get_completion_candidates(text)

        try:
            return self.completion_candidates[state]
        except IndexError:
            return None

    def get_completion_candidates(self, text):
        matches = self.definitions.get_matching_names(text + "*")
        if "`" not in text:
            matches = [strip_context(m) for m in matches]
        return matches

    def reset_lineno(self):
        self.lineno = 0

    def feed(self):
        result = self.read_line(self.get_in_prompt()) + "\n"
        if result == "\n":
            return ""  # end of input
        self.lineno += 1
        return result

    def empty(self):
        return False


class TerminalOutput(Output):
    def max_stored_size(self, settings):
        return None

    def __init__(self, shell):
        self.shell = shell

    def out(self, out):
        return self.shell.out_callback(out)


def main() -> int:
    """
    Command-line entry.

    Return exit code we want to give status of
    """
    exit_rc = 0
    argparser = argparse.ArgumentParser(
        prog="mathics",
        usage="%(prog)s [options] [FILE]",
        add_help=False,
        description="A simple command-line interface to Mathics",
        epilog="""For a more extensive command-line interface see "mathicsscript".
Please contribute to Mathics!""",
    )

    argparser.add_argument(
        "FILE",
        nargs="?",
        type=argparse.FileType("r"),
        help="execute commands from FILE",
    )

    argparser.add_argument(
        "--help", "-h", help="show this help message and exit", action="help"
    )

    argparser.add_argument(
        "--full-form",
        "-F",
        help="Show how input was parsed to FullForm",
        action="store_true",
    )

    argparser.add_argument(
        "--pyextensions",
        "-l",
        action="append",
        metavar="PYEXT",
        help="directory to load extensions in python",
    )

    argparser.add_argument(
        "--persist",
        help="go to interactive shell after evaluating FILE or -e",
        action="store_true",
    )

    # --initfile is different from the combination FILE --persist since the first one
    # leaves the history empty and sets the current $Line to 1.
    argparser.add_argument(
        "--initfile",
        help="the same that FILE and --persist together",
        type=argparse.FileType("r"),
    )

    argparser.add_argument(
        "--quiet", "-q", help="don't print message at startup", action="store_true"
    )

    argparser.add_argument(
        "-script", help="run a mathics file in script mode", action="store_true"
    )

    argparser.add_argument(
        "--execute",
        "-e",
        action="append",
        metavar="EXPR",
        help="evaluate EXPR before processing any input files (may be given "
        "multiple times)",
    )

    argparser.add_argument(
        "--colors",
        nargs="?",
        help="interactive shell colors. Use value 'NoColor' or 'None' to disable ANSI color decoration",
    )

    argparser.add_argument(
        "--no-completion", help="disable tab completion", action="store_true"
    )

    argparser.add_argument(
        "--no-readline",
        help="disable line editing (implies --no-completion)",
        action="store_true",
    )

    argparser.add_argument(
        "--version", "-v", action="version", version="%(prog)s " + __version__
    )

    argparser.add_argument(
        "--strict-wl-output",
        help="Most WL-output compatible (at the expense of useability).",
        action="store_true",
    )

    argparser.add_argument(
        "--trace-builtins",
        "-T",
        help="Trace Built-in call counts and elapsed time",
        action="store_true",
    )

    args, script_args = argparser.parse_known_args()

    quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-D"

    extension_modules = []
    if args.pyextensions:
        for ext in args.pyextensions:
            extension_modules.append(ext)
    else:
        from mathics.settings import default_pymathics_modules

        extension_modules = default_pymathics_modules

    if args.trace_builtins:
        BuiltinRule.do_replace = traced_do_replace
        import atexit

        def dump_tracing_stats():
            TraceBuiltins.dump_tracing_stats(sort_by="count", evaluation=None)

        atexit.register(dump_tracing_stats)

    definitions = Definitions(add_builtin=True, extension_modules=extension_modules)
    definitions.set_line_no(0)

    shell = TerminalShell(
        definitions,
        args.colors,
        want_readline=not (args.no_readline),
        want_completion=not (args.no_completion),
    )

    if args.initfile:
        feeder = MathicsFileLineFeeder(args.initfile)
        try:
            while not feeder.empty():
                evaluation = Evaluation(
                    shell.definitions,
                    output=TerminalOutput(shell),
                    catch_interrupt=False,
                )
                query = evaluation.parse_feeder(feeder)
                if query is None:
                    continue
                evaluation.evaluate(query, timeout=settings.TIMEOUT)
        except (KeyboardInterrupt):
            print("\nKeyboardInterrupt")

        definitions.set_line_no(0)

    if args.FILE is not None:
        feeder = MathicsFileLineFeeder(args.FILE)
        try:
            while not feeder.empty():
                evaluation = Evaluation(
                    shell.definitions,
                    output=TerminalOutput(shell),
                    catch_interrupt=False,
                )
                query = evaluation.parse_feeder(feeder)
                if query is None:
                    continue
                evaluation.evaluate(query, timeout=settings.TIMEOUT)
        except (KeyboardInterrupt):
            print("\nKeyboardInterrupt")

        if args.persist:
            definitions.set_line_no(0)
        elif not args.execute:
            return exit_rc

    if args.execute:
        for expr in args.execute:
            evaluation = Evaluation(shell.definitions, output=TerminalOutput(shell))
            result = evaluation.parse_evaluate(expr, timeout=settings.TIMEOUT)
            shell.print_result(
                result, no_out_prompt=True, strict_wl_output=args.strict_wl_output
            )
            if evaluation.exc_result is Symbol("Null"):
                exit_rc = 0
            elif evaluation.exc_result is Symbol("$Aborted"):
                exit_rc = -1
            elif evaluation.exc_result is Symbol("Overflow"):
                exit_rc = -2
            else:
                exit_rc = -3

        if not args.persist:
            return exit_rc

    if not args.quiet:
        print()
        print(version_string + "\n")
        print(license_string + "\n")
        print(f"Quit by evaluating Quit[] or by pressing {quit_command}.\n")

    while True:
        try:
            evaluation = Evaluation(shell.definitions, output=TerminalOutput(shell))
            query, source_code = evaluation.parse_feeder_returning_code(shell)
            if len(source_code) and source_code[0] == "!":
                subprocess.run(source_code[1:], shell=True)
                shell.definitions.increment_line_no(1)
                continue
            if query is None:
                continue
            if args.full_form:
                print(query)
            result = evaluation.evaluate(query, timeout=settings.TIMEOUT)
            if result is not None:
                shell.print_result(result, strict_wl_output=args.strict_wl_output)
        except (KeyboardInterrupt):
            print("\nKeyboardInterrupt")
        except EOFError:
            print("\n\nGoodbye!\n")
            break
        except SystemExit:
            print("\n\nGoodbye!\n")
            # raise to pass the error code on, e.g. Quit[1]
            raise
        finally:
            shell.reset_lineno()
    return exit_rc


if __name__ == "__main__":
    sys.exit(main())
