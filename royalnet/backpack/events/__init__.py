# Imports go here!
from .exception import ExceptionEvent

# Enter the commands of your Pack here!
available_events = [

]

# noinspection PyUnreachableCode
if __debug__:
    available_events.append(ExceptionEvent)

# Don't change this, it should automatically generate __all__
__all__ = [command.__name__ for command in available_events]
