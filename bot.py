"""Абстракция бота, торгующего на маркете
API:
Bot(config_filename) - конструктор
bot.login()
bot.logout()
bot.createBuyOrder()
bot.createSellOrder()

"""
import os
import re
import json
import pickle
from time import sleep

import requests
from bs4 import BeautifulSoup
from steampy import guard
from steampy.confirmation import ConfirmationExecutor
from steampy.client import SteamClient, Asset, SteamMarket
from steampy.models import GameOptions, SteamUrl, Currency
from steampy.exceptions import ConfirmationExpected, LoginRequired

# from market import Market
from utils import load_json, dump_json
# from inventory import Inventory, GameInventory, CommunityInventory

SteamUrl.APIKEY_URL = 'https://steamcommunity.com/dev/apikey'

# def _get_item_price(tag):
#     """
#     :tag
#     :returns (price_with_fee, price_without_fee)"""
#     def clear_price(price):
#         price = price.strip().split(" ")[0]
#         return int(float(price.replace(',', '.')) * 100)
#
#     price_with_fee = tag.find('span', class_='market_listing_price_with_fee').string
#     price_without_fee = tag.find('span', class_='market_listing_price_without_fee').string
#     return (clear_price(price_with_fee), clear_price(price_without_fee))


# def _get_listing_params(tag):
#     """:returns [listing_id, appid, contextid, assetid]"""
#     item_params = tag.find('div', class_='market_listing_price_listings_block')
#     link = item_params.find('a').get('href')
#     result_list = re.findall(r"\d+", link)
#     return result_list


class Bot(SteamClient):
    def __init__(self, config: str):
        self.cred = load_json(config)
        self.cancel_existing_orders = True
        self.steamid = self.cred.get('steamid')
        super().__init__(
            self.cred.get('api'),
            username=self.cred.get('login'),
            password=self.cred.get('password'),
            steam_guard=config
        )
        self.session_dir = os.getcwd() + '/session/'
        # self.steam_guard_str = config_name
        self.config = config

        # self.inventory = Inventory(self)
        self.load_session()
        self.do_login()
        # self.market = SteamMarket(self._session)
        if self.cred.get('api') == '':
            try:
                self._api_key = self._get_apikey_from_html()
            except AttributeError: # ошибка может появляться если аккаунт создан, но еще не активирован маркет. Ключ api можно получить после пополнения баланса на 5$
                self._api_key = ''
            self.cred.update({"api": self._api_key})
            dump_json(self.config, self.cred)

    def __str__(self):
        return f"<Bot object. Username: {self.username}>"

    def _get_apikey_from_html(self):
        """Импорт api ключа"""
        req = self._session.get(SteamUrl.APIKEY_URL)
        soup = BeautifulSoup(req.text, features="html.parser")
        p_tags = soup.find('div', id='bodyContents_ex').find_all('p')
        for p_tag in p_tags:
            if 'Key' in p_tag.string:
                print("API Key imported.")
                return p_tag.string.split(" ")[1]

    def load_session(self):
        try:
            print("Load session: ", end='')
            with open('{}session_{}.pkl'.format(self.session_dir, self.username), 'rb') as f:
                self._session = pickle.load(f)
        except FileNotFoundError:
            print("new session created")
            self._session = requests.Session()
        else:
            self.was_login_executed = True
            print("successful")

    def save_session(self, session):
        if 'session' not in os.listdir(os.getcwd()):
            os.mkdir(self.session_dir)
        with open('{}session_{}.pkl'.format(self.session_dir, self.username), 'wb') as f:
            pickle.dump(session, f)

    def do_login(self):
        """Аутентификация."""
        try:
            if not self.is_session_alive():
                raise LoginRequired
        except LoginRequired:
            print(f'Bot <{self.username}>: Logging in...', end='')
            self.login(self.username, self._password, self.config)
            sleep(5)
            self.save_session(self._session)
            print('ok!')
        else:
            print(f'Bot <{self.username}> already logged in')
            self.steam_guard = guard.load_steam_guard(self.config)
        finally:
            self.was_login_executed = True
            self.market = SteamMarket(self._session)
            self.market._set_login_executed(self.steam_guard, self._get_session_id())

    def get_total_sell_listings(self):
        try:
            response = self._session.get(SteamUrl.COMMUNITY_URL + '/market/')
        except:
            return '0'
        else:
            soup = BeautifulSoup(response.text, 'lxml')
            try:
                my_market_selllistings_number = soup.find('span', id='my_market_selllistings_number').text
            except:
                my_market_selllistings_number = '0'
            return my_market_selllistings_number

    def get_marketable_inventory(self, app_id='753', context_id='6', marketable=1) -> dict:
        inventory = self.get_my_inventory(GameOptions(app_id, context_id))
        marketable_inventory = {
            key: value for key, value in inventory.items() if inventory[key]['marketable'] == marketable}
        return marketable_inventory

    def get_statistic(self, collection):
        """Собирает в кучу статистику."""
        balance = self.get_wallet_balance()
        sell_listing_number = self.get_total_sell_listings()
        total_orders = collection.get_total_orders()[0]

        try:
            inventory = self.get_marketable_inventory(marketable=0)
        except:
            print('Can\'t get Daily stats')
            return False
        else:
            r = get_marketable_cards_sorted_by_date(inventory)
            result = list_dates_to_string(r)

        try:
            total_cards_to_sell = self.get_marketable_inventory()
        except:
            total_cards_to_sell = []

        print(f"Balance: {balance}", end='')
        print(f'Daily stats: {result}', end='')
        print(f'Total buy orders: {total_orders}', end='')
        print(f'Total cards to sell: {len(total_cards_to_sell)}', end='')
        print(f'Sell listings number: {sell_listing_number}', end='')

        stats = {
            'Balance': balance,
            'Daily_stats': result,
            'Total_buy_orders': total_orders,
            'Sell_listings_number': sell_listing_number,
            'Total_cards_to_sell': len(total_cards_to_sell)
        }
        return stats

    def send_gift(self, assetid, email):
        data = {
            'GifteeAccountID': 0,
            'GifteeEmail': email,
            'GifteeName': '',
            'GiftMessage': '',
            'GiftSentiment': '',
            'GiftSignature': '',
            'ScheduledSendOnDate': 0,
            'GiftGID': assetid,
            'SessionID': self._get_session_id(),
            'IsReschedule': False
        }
        headers = {'Referer': SteamUrl.STORE_URL + '/checkout/sendgift/{}'.format(assetid)}
        self._session.post(SteamUrl.STORE_URL + '/checkout/sendgiftsubmit/', data,
                                      headers=headers)

    def save(self, path):
        pickle.dump(self, open(f'{path}{self.username}.bot', 'wb'))

    def confirm_awaiting_list(self):
        """Подтверждает продажу предметов находящихся в awaiting list"""
        con_executor = ConfirmationExecutor(self.market._steam_guard['identity_secret'],
                                            self.market._steam_guard['steamid'],
                                            self.market._session)
        confirmations = con_executor._get_confirmations()
        for confirmation in confirmations:
            con_executor._send_confirmation(confirmation)

    def send_friend_request(self, steamid):
        request_url = SteamUrl.COMMUNITY_URL + '/actions/AddFriendAjax'
        headers = {'Referer': SteamUrl.COMMUNITY_URL + f'/profiles/{steamid}/'}
        data = {'accept_invite': 0,
                'steamid': steamid,
                'sessionID': self._get_session_id()}
        return self._session.post(request_url, data, headers=headers).json()

    def accept_friend_request(self, steamid):
        url = SteamUrl.COMMUNITY_URL + f'/profiles/{self.steamid}/friends/action'
        headers = {'Referer': SteamUrl.COMMUNITY_URL + f'/{self.steamid}/friends/pending'}
        data = {
            'ajax': 1,
            'action': 'accept',
            'accept_invite': 0,
            'steamid': self.steamid,
            'steamids[]': steamid,
            'sessionid': self._get_session_id()
        }
        return self._session.post(url, data, headers=headers).json()

    def setup_profile(self):
        """
        Производит первоначальную настройку аккаунта для возможности принимать запросы в друзья
        адрес профиля: https://steamcommunity.com/profiles/{steam_id}
        :param bot:
        :return:
        """
        url = '{url}/profiles/{steam_id}/edit?welcomed=1'.format(url=SteamUrl.COMMUNITY_URL, steam_id=self.steamid)
        response = self._session.get(url)
        return response.text


def to_be_friends(bot1, bot2):
    '''как подружить два аккаунта'''
    bot2.setup_profile()
    sleep(1)
    print(bot1.send_friend_request(bot2.steamid))
    sleep(1)
    print(bot2.accept_friend_request(bot1.steamid))


if __name__ == '__main__':
    config = r'C:\Users\User\my_files\work\Steam\Steambots_configs\lostsoul53.json'
    bot = Bot(config)

