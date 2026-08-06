"""
Builds the `meridian_cpp_engine` Python extension from cpp/tick_engine.cpp.

Usage:
    pip install pybind11
    python setup.py build_ext --inplace

This produces a compiled .so (Linux/Mac) or .pyd (Windows) module importable
as `meridian_cpp_engine`. app/cpp_tick_engine.py imports it and falls back
gracefully to the pure-Python/numpy tick simulator if the extension hasn't
been built -- see that file for the fallback logic.
"""
from setuptools import setup, Extension
import pybind11

ext_modules = [
    Extension(
        "meridian_cpp_engine",
        ["cpp/tick_engine.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=["-O3", "-std=c++17"],
        # Deliberately NOT using -march=native here: this extension may be
        # built on a different machine (or Docker build stage) than it runs
        # on, and -march=native can bake in CPU instruction extensions that
        # cause an "illegal instruction" crash on a different deploy target.
        # Portable -O3 alone still clears >3M ticks/sec in testing, well
        # past the 1M records/sec target, so the safety tradeoff costs
        # nothing that matters here.
    ),
]

setup(
    name="meridian_cpp_engine",
    version="1.0.0",
    description="Meridian C++ tick generation + OHLCV aggregation engine",
    ext_modules=ext_modules,
)
