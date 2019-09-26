import telegram
import telegram.utils.request
import typing
import uuid
import urllib3
import asyncio
import sentry_sdk
import logging as _logging
from .generic import GenericBot
from ..utils import *
from ..error import *
from ..network import *
from ..database import *
from ..commands import *


log = _logging.getLogger(__name__)


class TelegramConfig:
    """The specific configuration to be used for :py:class:`royalnet.database.TelegramBot`."""
    def __init__(self, token: str):
        self.token: str = token


class TelegramBot(GenericBot):
    """A bot that connects to `Telegram <https://telegram.org/>`_."""
    interface_name = "telegram"

    def _init_client(self):
        """Create the :py:class:`telegram.Bot`, and set the starting offset."""
        # https://github.com/python-telegram-bot/python-telegram-bot/issues/341
        request = telegram.utils.request.Request(20, read_timeout=15)
        self.client = telegram.Bot(self._telegram_config.token, request=request)
        self._offset: int = -100

    def _interface_factory(self) -> typing.Type[CommandInterface]:
        # noinspection PyPep8Naming
        GenericInterface = super()._interface_factory()

        # noinspection PyMethodParameters,PyAbstractClass
        class TelegramInterface(GenericInterface):
            name = self.interface_name
            prefix = "/"

            def __init__(self):
                super().__init__()
                self.keys_callbacks: typing.Dict[typing.Tuple[int, str], typing.Callable] = {}

            def register_keyboard_key(interface, key_name: str, callback: typing.Callable):
                interface.keys_callbacks[key_name] = callback

            def unregister_keyboard_key(interface, key_name: str):
                try:
                    del interface.keys_callbacks[key_name]
                except KeyError:
                    raise KeyError(f"Key '{key_name}' is not registered")

        return TelegramInterface

    def _data_factory(self) -> typing.Type[CommandData]:
        # noinspection PyMethodParameters,PyAbstractClass
        class TelegramData(CommandData):
            def __init__(data, interface: CommandInterface, update: telegram.Update):
                data.interface = interface
                data.update = update

            async def reply(data, text: str):
                await TelegramBot.safe_api_call(data.update.effective_chat.send_message,
                                                telegram_escape(text),
                                                parse_mode="HTML",
                                                disable_web_page_preview=True)

            async def get_author(data, error_if_none=False):
                if data.update.message is not None:
                    user: telegram.User = data.update.message.from_user
                elif data.update.callback_query is not None:
                    user: telegram.user = data.update.callback_query.from_user
                else:
                    raise UnregisteredError("Author can not be determined")
                if user is None:
                    if error_if_none:
                        raise UnregisteredError("No author for this message")
                    return None
                query = data.interface.session.query(self.master_table)
                for link in self.identity_chain:
                    query = query.join(link.mapper.class_)
                query = query.filter(self.identity_column == user.id)
                result = await asyncify(query.one_or_none)
                if result is None and error_if_none:
                    raise UnregisteredError("Author is not registered")
                return result

            async def keyboard(data, text: str, keyboard: typing.Dict[str, typing.Callable]) -> None:
                tg_keyboard = []
                for key in keyboard:
                    press_id = uuid.uuid4()
                    tg_keyboard.append([telegram.InlineKeyboardButton(key, callback_data=str(press_id))])
                    data.interface.register_keyboard_key(key_name=str(press_id), callback=keyboard[key])
                await TelegramBot.safe_api_call(data.update.effective_chat.send_message,
                                                telegram_escape(text),
                                                reply_markup=telegram.InlineKeyboardMarkup(tg_keyboard),
                                                parse_mode="HTML",
                                                disable_web_page_preview=True)

            async def delete_invoking(data, error_if_unavailable=False) -> None:
                message: telegram.Message = data.update.message
                await TelegramBot.safe_api_call(message.delete)

        return TelegramData

    def __init__(self, *,
                 telegram_config: TelegramConfig,
                 royalnet_config: typing.Optional[RoyalnetConfig] = None,
                 database_config: typing.Optional[DatabaseConfig] = None,
                 sentry_dsn: typing.Optional[str] = None,
                 commands: typing.List[typing.Type[Command]] = None):
        super().__init__(royalnet_config=royalnet_config,
                         database_config=database_config,
                         sentry_dsn=sentry_dsn,
                         commands=commands)
        self._telegram_config = telegram_config
        self._init_client()

    @staticmethod
    async def safe_api_call(f: typing.Callable, *args, **kwargs) -> typing.Optional:
        while True:
            try:
                return await asyncify(f, *args, **kwargs)
            except telegram.error.TimedOut as error:
                log.debug(f"Timed out during {f.__qualname__} (retrying in 15s): {error}")
                await asyncio.sleep(15)
                continue
            except telegram.error.NetworkError as error:
                log.debug(f"Network error during {f.__qualname__} (skipping): {error}")
                break
            except telegram.error.Unauthorized as error:
                log.info(f"Unauthorized to run {f.__qualname__} (skipping): {error}")
                break
            except telegram.error.RetryAfter as error:
                log.warning(f"Rate limited during {f.__qualname__} (retrying in 15s): {error}")
                await asyncio.sleep(15)
                continue
            except urllib3.exceptions.HTTPError as error:
                log.warning(f"urllib3 HTTPError during {f.__qualname__} (retrying in 15s): {error}")
                await asyncio.sleep(15)
                continue
            except Exception as error:
                log.error(f"{error.__class__.__qualname__} during {f} (skipping): {error}")
                sentry_sdk.capture_exception(error)
                break
        return None

    async def _handle_update(self, update: telegram.Update):
        # Skip non-message updates
        if update.message is not None:
            await self._handle_message(update)
        elif update.callback_query is not None:
            await self._handle_callback_query(update)

    async def _handle_message(self, update: telegram.Update):
        message: telegram.Message = update.message
        text: str = message.text
        # Try getting the caption instead
        if text is None:
            text: str = message.caption
        # No text or caption, ignore the message
        if text is None:
            return
        # Skip non-command updates
        if not text.startswith("/"):
            return
        # Find and clean parameters
        command_text, *parameters = text.split(" ")
        command_name = command_text.replace(f"@{self.client.username}", "").lower()
        # Send a typing notification
        await self.safe_api_call(update.message.chat.send_action, telegram.ChatAction.TYPING)
        # Find the command
        try:
            command = self.commands[command_name]
        except KeyError:
            # Skip the message
            return
        # Prepare data
        data = self._Data(interface=command.interface, update=update)
        # Run the command
        try:
            await command.run(CommandArgs(parameters), data)
        except InvalidInputError as e:
            await data.reply(f"⚠️ {' '.join(e.args)}\n"
                             f"Syntax: [c]/{command.name} {command.syntax}[/c]")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_message = f"🦀 [b]{e.__class__.__name__}[/b] 🦀\n"
            error_message += '\n'.join(e.args)
            await data.reply(error_message)
            if __debug__:
                raise

    async def _handle_callback_query(self, update: telegram.Update):
        query: telegram.CallbackQuery = update.callback_query
        source: telegram.Message = query.message
        callback: typing.Optional[typing.Callable] = None
        command: typing.Optional[Command] = None
        for command in self.commands.values():
            if query.data in command.interface.keys_callbacks:
                callback = command.interface.keys_callbacks[query.data]
                break
        if callback is None:
            await self.safe_api_call(source.edit_reply_markup, reply_markup=None)
            await self.safe_api_call(query.answer, text="⛔️ This keyboard has expired.")
            return
        try:
            response = await callback(data=self._Data(interface=command.interface, update=update))
        except KeyboardExpiredError:
            # FIXME: May cause a memory leak, as keys are not deleted after use
            await self.safe_api_call(source.edit_reply_markup, reply_markup=None)
            await self.safe_api_call(query.answer, text="⛔️ This keyboard has expired.")
            return
        except Exception as e:
            error_text = f"⛔️ {e.__class__.__name__}\n"
            error_text += '\n'.join(e.args)
            await self.safe_api_call(query.answer, text=error_text)
            return
        else:
            await self.safe_api_call(query.answer, text=response)

    async def run(self):
        while True:
            # Get the latest 100 updates
            last_updates: typing.List[telegram.Update] = await self.safe_api_call(self.client.get_updates,
                                                                                  offset=self._offset,
                                                                                  timeout=30,
                                                                                  read_latency=5.0)
            # Handle updates
            for update in last_updates:
                # noinspection PyAsyncCall
                self.loop.create_task(self._handle_update(update))
            # Recalculate offset
            try:
                self._offset = last_updates[-1].update_id + 1
            except IndexError:
                pass
