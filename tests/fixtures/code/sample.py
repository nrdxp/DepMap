"""Sample Python module for testing symbol search."""


def hello_world():
    """Greet the world."""
    return "Hello, World!"


def calculate_sum(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


class SampleClass:
    """A sample class with methods."""

    def __init__(self, name: str):
        self.name = name

    def method_one(self) -> str:
        """First method."""
        return f"Hello, {self.name}"

    def method_two(self, value: int) -> int:
        """Second method."""
        return value * 2


GLOBAL_CONSTANT = 42
