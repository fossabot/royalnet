# Imports go here!
from .roll import RollCommand
from .dice import DiceCommand
from .dndactive import DndactiveCommand
from .dndinfo import DndinfoCommand
from .dndnew import DndnewCommand
from .dndedit import DndeditCommand
from .dndroll import DndrollCommand
from .dndrolladv import DndrolladvCommand
from .dndrolldis import DndrolldisCommand

# Enter the commands of your Pack here!
available_commands = [
    RollCommand,
    DiceCommand,
    DndactiveCommand,
    DndinfoCommand,
    DndnewCommand,
    DndeditCommand,
    DndrollCommand,
    DndrolladvCommand,
    DndrolldisCommand,
]

# Don't change this, it should automatically generate __all__
__all__ = [command.__class__.__qualname__ for command in available_commands]