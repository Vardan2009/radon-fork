from core.errors import *
from core.datatypes import *
from core.parser import RTResult
from core.builtin_funcs import BuiltInFunction


class BuiltInClass(BaseClass):
    def __init__(self, name, instance_class):
        super().__init__(name)
        self.instance_class = instance_class

    def create(self, args):
        inst = BuiltInInstance(self)
        return RTResult().success(inst.set_context(self.context).set_pos(self.pos_start, self.pos_end))

    def init(self, inst, args, kwargs):
        res = RTResult()
        if len(kwargs) > 0:
            return res.failure(
                RTError(
                    list(kwargs.values())[0].pos_start,
                    list(kwargs.values())[-1].pos_end,
                    "Keyword arguments are not yet supported for built-in functions.",
                    list(kwargs.values())[0].context,
                )
            )
        _, error = inst.operator("__constructor__", args)
        if error:
            return res.failure(error)
        return res.success(None)

    def get(self, name):
        return None, self.illegal_operation(name)

    def __repr__(self):
        return f"<built-in class {self.name}>"


class BuiltInInstance(BaseInstance):
    def __init__(self, parent_class):
        super().__init__(parent_class, parent_class.instance_class.__symbol_table__)
        self.instance_class = parent_class.instance_class
        self.symbol_table.set("this", self)

    def operator(self, operator, *args):
        try:
            op = self.instance_class.__operators__[operator]
        except KeyError:
            return None, self.illegal_operation(*args)
        res = RTResult()
        value = res.register(op(self, *args))
        if res.should_return():
            return None, res.error
        return value, None


class BuiltInObjectMeta(type):
    def __new__(cls, class_name, bases, attrs):
        if class_name == "BuiltInObject":
            return type.__new__(cls, class_name, bases, attrs)

        operators = {}
        symbols = {}
        for name, value in attrs.items():
            if hasattr(value, "__operator__"):
                operators[value.__operator__] = value
            elif hasattr(value, "__is_method__") and value.__is_method__:
                assert hasattr(value, "arg_names"), "Make sure to use the args() decorator on any built-in methods!"
                assert hasattr(value, "defaults"), "Unreachable. The first `assert` should have ensured this."
                symbols[name] = bif = BuiltInFunction(value.__name__, value)
        symbol_table = SymbolTable(None)
        symbol_table.symbols = symbols

        attrs["__symbol_table__"] = symbol_table
        attrs["__operators__"] = operators
        return type.__new__(cls, class_name, bases, attrs)


class BuiltInObject(metaclass=BuiltInObjectMeta):
    pass


# Decorators for methods and operators
def operator(dunder):
    def _deco(f):
        f.__operator__ = dunder
        return f

    return _deco


def method(f):
    f.__is_method__ = True
    return f


# Decorator to check argument types
def check(types, defaults=None):
    if defaults is None:
        defaults = [None] * len(types)

    def _deco(f):
        def wrapper(self, args):
            res = RTResult()
            func_name = f.__name__
            class_name = self.parent_class.name
            full_func_name = f"{class_name}.{func_name}()"

            # Check arg count
            if len(args) > len(types):
                return res.failure(
                    RTError(
                        self.pos_start,
                        self.pos_end,
                        f"{len(args) - len(types)} too many args passed into {full_func_name}",
                        self.context,
                    )
                )

            if len(args) < len(types) - len(list(filter(lambda default: default is not None, defaults))):
                return res.failure(
                    RTError(
                        self.pos_start,
                        self.pos_end,
                        f"{(len(types) - len(list(filter(lambda default: default is not None, defaults)))) - len(args)} too few args passed into {full_func_name}",
                        self.context,
                    )
                )

            # Populate defaults
            real_args = []
            for i, typ in enumerate(types):
                arg = defaults[i] if i >= len(args) else args[i]
                assert arg is not None, "We should have already errored"
                if not isinstance(arg, typ):
                    return res.failure(
                        RTError(
                            self.pos_start,
                            self.pos_end,
                            f"Expected {typ.__name__} for argument {i} (0-based) of {full_func_name}, got {arg.__class__.__name__} instead",
                            self.context,
                        )
                    )
                real_args.append(arg)
            return f(self, *real_args)

        wrapper.__name__ = f.__name__
        return wrapper

    return _deco
