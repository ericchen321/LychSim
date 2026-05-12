# Borrowed from HuggingFace Transformers: transformers.utils.generic.py
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from functools import partial
import importlib.util
import logging
import os
from packaging import version
from typing import Any, Union

__all__ = ['ModelOutput']


# TODO: This doesn't work for all packages (`bs4`, `faiss`, etc.) Talk to Sylvain to see how to do with it better.
def _is_package_available(pkg_name: str, return_version: bool = False) -> Union[tuple[bool, str], bool]:
    # Check if the package spec exists and grab its version to avoid importing a local directory
    package_exists = importlib.util.find_spec(pkg_name) is not None
    package_version = "N/A"
    if package_exists:
        try:
            # TODO: Once python 3.9 support is dropped, `importlib.metadata.packages_distributions()`
            # should be used here to map from package name to distribution names
            # e.g. PIL -> Pillow, Pillow-SIMD; quark -> amd-quark; onnxruntime -> onnxruntime-gpu.
            # `importlib.metadata.packages_distributions()` is not available in Python 3.9.

            # Primary method to get the package version
            package_version = importlib.metadata.version(pkg_name)
        except importlib.metadata.PackageNotFoundError:
            # Fallback method: Only for "torch" and versions containing "dev"
            if pkg_name == "torch":
                try:
                    package = importlib.import_module(pkg_name)
                    temp_version = getattr(package, "__version__", "N/A")
                    # Check if the version contains "dev"
                    if "dev" in temp_version:
                        package_version = temp_version
                        package_exists = True
                    else:
                        package_exists = False
                except ImportError:
                    # If the package can't be imported, it's not available
                    package_exists = False
            elif pkg_name == "quark":
                # TODO: remove once `importlib.metadata.packages_distributions()` is supported.
                try:
                    package_version = importlib.metadata.version("amd-quark")
                except Exception:
                    package_exists = False
            else:
                # For packages other than "torch", don't attempt the fallback and set as not available
                package_exists = False
        logging.debug(f"Detected {pkg_name} version: {package_version}")
    if return_version:
        return package_exists, package_version
    else:
        return package_exists


ENV_VARS_TRUE_VALUES = {"1", "ON", "YES", "TRUE"}
ENV_VARS_TRUE_AND_AUTO_VALUES = ENV_VARS_TRUE_VALUES.union({"AUTO"})
USE_TF = os.environ.get("USE_TF", "AUTO").upper()
USE_TORCH = os.environ.get("USE_TORCH", "AUTO").upper()
USE_JAX = os.environ.get("USE_FLAX", "AUTO").upper()

FORCE_TF_AVAILABLE = os.environ.get("FORCE_TF_AVAILABLE", "AUTO").upper()

_torch_version = "N/A"
_torch_available = False
if USE_TORCH in ENV_VARS_TRUE_AND_AUTO_VALUES and USE_TF not in ENV_VARS_TRUE_VALUES:
    _torch_available, _torch_version = _is_package_available("torch", return_version=True)
    if _torch_available:
        _torch_available = version.parse(_torch_version) >= version.parse("2.1.0")
        if not _torch_available:
            logging.warning(f"Disabling PyTorch because PyTorch >= 2.1 is required but found {_torch_version}")
else:
    logging.info("Disabling PyTorch because USE_TF is set")
    _torch_available = False

_flax_available = False
if USE_JAX in ENV_VARS_TRUE_AND_AUTO_VALUES:
    _flax_available, _flax_version = _is_package_available("flax", return_version=True)
    if _flax_available:
        _jax_available, _jax_version = _is_package_available("jax", return_version=True)
        if _jax_available:
            logging.info(f"JAX version {_jax_version}, Flax version {_flax_version} available.")
        else:
            _flax_available = _jax_available = False
            _jax_version = _flax_version = "N/A"

_tf_version = "N/A"
_tf_available = False
if FORCE_TF_AVAILABLE in ENV_VARS_TRUE_VALUES:
    _tf_available = True
else:
    if USE_TF in ENV_VARS_TRUE_AND_AUTO_VALUES and USE_TORCH not in ENV_VARS_TRUE_VALUES:
        # Note: _is_package_available("tensorflow") fails for tensorflow-cpu. Please test any changes to the line below
        # with tensorflow-cpu to make sure it still works!
        _tf_available = importlib.util.find_spec("tensorflow") is not None
        if _tf_available:
            candidates = (
                "tensorflow",
                "tensorflow-cpu",
                "tensorflow-gpu",
                "tf-nightly",
                "tf-nightly-cpu",
                "tf-nightly-gpu",
                "tf-nightly-rocm",
                "intel-tensorflow",
                "intel-tensorflow-avx512",
                "tensorflow-rocm",
                "tensorflow-macos",
                "tensorflow-aarch64",
            )
            _tf_version = None
            # For the metadata, we have to look for both tensorflow and tensorflow-cpu
            for pkg in candidates:
                try:
                    _tf_version = importlib.metadata.version(pkg)
                    break
                except importlib.metadata.PackageNotFoundError:
                    pass
            _tf_available = _tf_version is not None
        if _tf_available:
            if version.parse(_tf_version) < version.parse("2"):
                logging.info(
                    f"TensorFlow found but with version {_tf_version}. Transformers requires version 2 minimum."
                )
                _tf_available = False
    else:
        logging.info("Disabling Tensorflow because USE_TORCH is set")

_mlx_available = _is_package_available("mlx")


def is_torch_available():
    return _torch_available


def get_torch_version():
    return _torch_version


def is_tf_available():
    return _tf_available


def is_mlx_available():
    return _mlx_available


def _is_torch(x):
    import torch

    return isinstance(x, torch.Tensor)


def is_torch_tensor(x):
    """
    Tests if `x` is a torch tensor or not. Safe to call even if torch is not installed.
    """
    return False if not is_torch_available() else _is_torch(x)


def _is_tensorflow(x):
    import tensorflow as tf

    return isinstance(x, tf.Tensor)


def is_tf_tensor(x):
    """
    Tests if `x` is a tensorflow tensor or not. Safe to call even if tensorflow is not installed.
    """
    return False if not is_tf_available() else _is_tensorflow(x)


def _is_jax(x):
    import jax.numpy as jnp  # noqa: F811

    return isinstance(x, jnp.ndarray)


def is_jax_tensor(x):
    """
    Tests if `x` is a Jax tensor or not. Safe to call even if jax is not installed.
    """
    return False if not is_flax_available() else _is_jax(x)


def _is_numpy(x):
    import numpy as np

    return isinstance(x, np.ndarray)


def is_numpy_array(x):
    """
    Tests if `x` is a numpy array or not.
    """
    return _is_numpy(x)


def _is_mlx(x):
    import mlx.core as mx

    return isinstance(x, mx.array)


def is_mlx_array(x):
    """
    Tests if `x` is a mlx array or not. Safe to call even when mlx is not installed.
    """
    return False if not is_mlx_available() else _is_mlx(x)


def infer_framework_from_repr(x):
    """
    Tries to guess the framework of an object `x` from its repr (brittle but will help in `is_tensor` to try the
    frameworks in a smart order, without the need to import the frameworks).
    """
    representation = str(type(x))
    if representation.startswith("<class 'torch."):
        return "pt"
    elif representation.startswith("<class 'tensorflow."):
        return "tf"
    elif representation.startswith("<class 'jax"):
        return "jax"
    elif representation.startswith("<class 'numpy."):
        return "np"
    elif representation.startswith("<class 'mlx."):
        return "mlx"


def _get_frameworks_and_test_func(x):
    """
    Returns an (ordered since we are in Python 3.7+) dictionary framework to test function, which places the framework
    we can guess from the repr first, then Numpy, then the others.
    """
    framework_to_test = {
        "pt": is_torch_tensor,
        "tf": is_tf_tensor,
        "jax": is_jax_tensor,
        "np": is_numpy_array,
        "mlx": is_mlx_array,
    }
    preferred_framework = infer_framework_from_repr(x)
    # We will test this one first, then numpy, then the others.
    frameworks = [] if preferred_framework is None else [preferred_framework]
    if preferred_framework != "np":
        frameworks.append("np")
    frameworks.extend([f for f in framework_to_test if f not in [preferred_framework, "np"]])
    return {f: framework_to_test[f] for f in frameworks}


def is_torch_fx_available():
    return is_torch_available()


def is_torch_fx_proxy(x):
    if is_torch_fx_available():
        import torch.fx

        return isinstance(x, torch.fx.Proxy)
    return False


def is_flax_available():
    return _flax_available


def is_tensor(x):
    """
    Tests if `x` is a `torch.Tensor`, `tf.Tensor`, `jaxlib.xla_extension.DeviceArray`, `np.ndarray` or `mlx.array`
    in the order defined by `infer_framework_from_repr`
    """
    # This gives us a smart order to test the frameworks with the corresponding tests.
    framework_to_test_func = _get_frameworks_and_test_func(x)
    for test_func in framework_to_test_func.values():
        if test_func(x):
            return True

    # Tracers
    if is_torch_fx_proxy(x):
        return True

    if is_flax_available():
        from jax.core import Tracer

        if isinstance(x, Tracer):
            return True

    return False


class ModelOutput(OrderedDict):
    """
    Base class for all model outputs as dataclass. Has a `__getitem__` that allows indexing by integer or slice (like a
    tuple) or strings (like a dictionary) that will ignore the `None` attributes. Otherwise behaves like a regular
    python dictionary.

    <Tip warning={true}>

    You can't unpack a `ModelOutput` directly. Use the [`~utils.ModelOutput.to_tuple`] method to convert it to a tuple
    before.

    </Tip>
    """

    def __init_subclass__(cls) -> None:
        """Register subclasses as pytree nodes.

        This is necessary to synchronize gradients when using `torch.nn.parallel.DistributedDataParallel` with
        `static_graph=True` with modules that output `ModelOutput` subclasses.
        """
        if is_torch_available():
            if version.parse(get_torch_version()) >= version.parse("2.2"):
                from torch.utils._pytree import register_pytree_node

                register_pytree_node(
                    cls,
                    _model_output_flatten,
                    partial(_model_output_unflatten, output_type=cls),
                    serialized_type_name=f"{cls.__module__}.{cls.__name__}",
                )
            else:
                from torch.utils._pytree import _register_pytree_node

                _register_pytree_node(
                    cls,
                    _model_output_flatten,
                    partial(_model_output_unflatten, output_type=cls),
                )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Subclasses of ModelOutput must use the @dataclass decorator
        # This check is done in __init__ because the @dataclass decorator operates after __init_subclass__
        # issubclass() would return True for issubclass(ModelOutput, ModelOutput) when False is needed
        # Just need to check that the current class is not ModelOutput
        is_modeloutput_subclass = self.__class__ != ModelOutput

        if is_modeloutput_subclass and not is_dataclass(self):
            raise TypeError(
                f"{self.__module__}.{self.__class__.__name__} is not a dataclass."
                " This is a subclass of ModelOutput and so must use the @dataclass decorator."
            )

    def __post_init__(self):
        """Check the ModelOutput dataclass.

        Only occurs if @dataclass decorator has been used.
        """
        class_fields = fields(self)

        # Safety and consistency checks
        if not len(class_fields):
            raise ValueError(f"{self.__class__.__name__} has no fields.")
        if not all(field.default is None for field in class_fields[1:]):
            raise ValueError(f"{self.__class__.__name__} should not have more than one required field.")

        first_field = getattr(self, class_fields[0].name)
        other_fields_are_none = all(getattr(self, field.name) is None for field in class_fields[1:])

        if other_fields_are_none and not is_tensor(first_field):
            if isinstance(first_field, dict):
                iterator = first_field.items()
                first_field_iterator = True
            else:
                try:
                    iterator = iter(first_field)
                    first_field_iterator = True
                except TypeError:
                    first_field_iterator = False

            # if we provided an iterator as first field and the iterator is a (key, value) iterator
            # set the associated fields
            if first_field_iterator:
                for idx, element in enumerate(iterator):
                    if (
                        not isinstance(element, (list, tuple))
                        or not len(element) == 2
                        or not isinstance(element[0], str)
                    ):
                        if idx == 0:
                            # If we do not have an iterator of key/values, set it as attribute
                            self[class_fields[0].name] = first_field
                        else:
                            # If we have a mixed iterator, raise an error
                            raise ValueError(
                                f"Cannot set key/value for {element}. It needs to be a tuple (key, value)."
                            )
                        break
                    setattr(self, element[0], element[1])
                    if element[1] is not None:
                        self[element[0]] = element[1]
            elif first_field is not None:
                self[class_fields[0].name] = first_field
        else:
            for field in class_fields:
                v = getattr(self, field.name)
                if v is not None:
                    self[field.name] = v

    def __delitem__(self, *args, **kwargs):
        raise Exception(f"You cannot use ``__delitem__`` on a {self.__class__.__name__} instance.")

    def setdefault(self, *args, **kwargs):
        raise Exception(f"You cannot use ``setdefault`` on a {self.__class__.__name__} instance.")

    def pop(self, *args, **kwargs):
        raise Exception(f"You cannot use ``pop`` on a {self.__class__.__name__} instance.")

    def update(self, *args, **kwargs):
        raise Exception(f"You cannot use ``update`` on a {self.__class__.__name__} instance.")

    def __getitem__(self, k):
        if isinstance(k, str):
            inner_dict = dict(self.items())
            return inner_dict[k]
        else:
            return self.to_tuple()[k]

    def __setattr__(self, name, value):
        if name in self.keys() and value is not None:
            # Don't call self.__setitem__ to avoid recursion errors
            super().__setitem__(name, value)
        super().__setattr__(name, value)

    def __setitem__(self, key, value):
        # Will raise a KeyException if needed
        super().__setitem__(key, value)
        # Don't call self.__setattr__ to avoid recursion errors
        super().__setattr__(key, value)

    def __reduce__(self):
        if not is_dataclass(self):
            return super().__reduce__()
        callable, _args, *remaining = super().__reduce__()
        args = tuple(getattr(self, field.name) for field in fields(self))
        return callable, args, *remaining

    def to_tuple(self) -> tuple[Any]:
        """
        Convert self to a tuple containing all the attributes/keys that are not `None`.
        """
        return tuple(self[k] for k in self.keys())


if is_torch_available():
    import torch.utils._pytree as _torch_pytree

    def _model_output_flatten(output: ModelOutput) -> tuple[list[Any], "_torch_pytree.Context"]:
        return list(output.values()), list(output.keys())

    def _model_output_unflatten(
        values: Iterable[Any],
        context: "_torch_pytree.Context",
        output_type=None,
    ) -> ModelOutput:
        return output_type(**dict(zip(context, values)))

    if version.parse(get_torch_version()) >= version.parse("2.2"):
        _torch_pytree.register_pytree_node(
            ModelOutput,
            _model_output_flatten,
            partial(_model_output_unflatten, output_type=ModelOutput),
            serialized_type_name=f"{ModelOutput.__module__}.{ModelOutput.__name__}",
        )
    else:
        _torch_pytree._register_pytree_node(
            ModelOutput,
            _model_output_flatten,
            partial(_model_output_unflatten, output_type=ModelOutput),
        )
