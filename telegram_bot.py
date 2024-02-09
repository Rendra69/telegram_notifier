from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.types import FSInputFile

from steampy.models import GameOptions
from bot import Bot as SteamBot
from game_sender import GameSender
from config import tg_bot_token, efrem_config


tg_bot = Bot(token=tg_bot_token)
dp = Dispatcher(tg_bot)


game_list = []
game_senders = []

def auth(func):
    """Бот принимает и обрабатывает сообщения только от ID: 98048131.
    Всех остальных ш"""
    async def wrapper(message):
        if message['from']['id'] != 98048131:
            return await message.reply('Access denied', reply=False)
        return await func(message)

    return wrapper

@dp.message_handler(commands=['start'])
@auth
async def start_command(message: types.Message):
    await message.reply("hello")
    global game_sender, steam_bot
    steam_bot = SteamBot(efrem_config)

    game_sender = GameSender(steam_bot)
    game_senders.append((game_sender, steam_bot))
    unsent_games = game_sender.inventory.get_unsent()
    total_games = game_sender.inventory.get_total_games()
    global game_list
    game_list = list(total_games.keys())
    unsent_games_str = ''
    for count, (game, qnt) in enumerate(total_games.items(), 1):
        unsent_games_str += f'{count}. {game}: {qnt}\n'
        # print(f'{count}. {game:40}{qnt}')
    # menu exit
    # print("\n0. Exit (save inventory to file)")
    await message.reply(f"\nGame Inventory:\n"
                        f"{unsent_games_str}\n"
                        "Enter the Game, you want to send, and the qnt. Use spacebar (example: 2 2)")

    # total_games = game_sender.inventory.get_total_games()
        # if games_to_send is not None:
        #     game_name, game_qnt = games_to_send
        #     game_sender.send_games(steam_bot.username, game_name, game_qnt)
        #     game_sender.update_inventory()
        # else:
        #     break


    # await message.reply(bot.get_my_inventory(GameOptions('753', '1')))
@dp.message_handler()
async def send_game(message: types.Message):

    game, qnt = message.text.split(' ')
    game = int(game)
    qnt = int(qnt)
    global game_list
    game_name = game_list[game-1]
    game_sender = game_senders[0][0]
    steam_bot = game_senders[0][1]
    game_sender.send_games(steam_bot.username, game_name, qnt)
    # получить последний файл и отправить его в чат
    await tg_bot.send_file()
    await message.reply(f"Your choice: \n{game_name} - {qnt} pcs")


if __name__ == '__main__':
    # steam_bot = SteamBot(efrem_config)
    # game_sender = GameSender(steam_bot)
    # unsent_games = game_sender.inventory.get_unsent()
    # total_games = game_sender.inventory.get_total_games()
    # print(total_games)
    executor.start_polling(dp)
