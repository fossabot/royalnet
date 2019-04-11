import asyncio
from ..utils import Command, Call, InvalidInputError


class PingCommand(Command):

    command_name = "ping"
    command_description = "Ping pong!"
    command_syntax = "[time_to_wait]"

    @classmethod
    async def common(cls, call: Call):
        try:
            time = int(call.args[0])
        except InvalidInputError:
            time = 0
        except ValueError:
            raise InvalidInputError("time_to_wait is not a number")
        await asyncio.sleep(time)
        await call.reply("🏓 Pong!")