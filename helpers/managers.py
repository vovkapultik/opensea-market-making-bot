import os
import json
import time
import random
import requests

from src.logger import log
from src import utils


class WalletsManager:
    def __init__(self, mnemonics_path):
        with open(mnemonics_path, 'r') as f:
            self.wallets = utils.get_addresses(json.load(f)['mnemonics'])
            self.get_balances()

    def get_balances(self, wallet=None):
        log.debug(f'Retrieving balances')

        wallets_list = [wallet] if wallet else self.wallets

        for address in wallets_list:
            self.wallets[address].update({'eth_balance': utils.get_eth_balance(address)})
            self.wallets[address].update(utils.get_nft_balance(address))

        log.debug(f'Balances retrieved successfully')

    def choose_wallet(self, side, owner=None, price=None):
        if side == 'buy':
            for address in self.wallets:
                if address != owner:
                    gas_price = utils.get_gas_price()
                    if gas_price:
                        amount = price + int(os.environ.get('GAS_AMOUNT_ON_BUY')) * gas_price
                        if self.wallets[address]['eth_balance'] > amount:
                            data = {
                                'address': address,
                                'mnemonic': self.wallets[address]['mnemonic'],
                                'balance': self.wallets[address]['eth_balance'],
                                'ok': True
                            }
                            self.wallets[address]['eth_balance'] -= amount

                            return data

            return {'ok': False}

        elif side == 'sell':
            for address in self.wallets:
                if len(self.wallets[address]['free_nft_balance']) >= 1:
                    data = {
                        'address': address,
                        'mnemonic': self.wallets[address]['mnemonic'],
                        'token_id': self.wallets[address]['free_nft_balance'][0],
                        'ok': True
                    }
                    self.wallets[address]['free_nft_balance'].pop(0)

                    return data

            return {'ok': False}

        return {'ok': False}

    def buy(self, listing):
        wallet_info = self.choose_wallet('buy', listing['owner'], listing['eth_price'])

        if wallet_info['ok']:

            log.info(f' --- Wallet {utils.shorten(wallet_info["address"])} will buy NFT #{listing["token_id"]} for'
                     f' {utils.shorten(listing["eth_price"])} / {utils.shorten(wallet_info["balance"])} ETH'
                     f' from {utils.shorten(listing["owner"])}')

            response = requests.post(
                url='http://0.0.0.0:7777/buy',
                json={
                    "password": "123",
                    "mnemonic": wallet_info["mnemonic"],
                    "network": os.environ.get("NETWORK_NAME"),
                    "buyer": wallet_info["address"],
                    "tokenId": listing["token_id"],
                    "tokenAddress": os.environ.get("CONTRACT_ADDRESS")
                }
            )

            print(response.text)
        else:
            log.warning(' --- Wallet with sufficient balance not found!')

    def sell(self, price):
        wallet_info = self.choose_wallet('sell')
        if wallet_info['ok']:
            log.info(f' --- Wallet {utils.shorten(wallet_info["address"])} will sell'
                     f' NFT #{wallet_info["token_id"]} for {utils.shorten(price)} ETH')

            response = requests.post(
                url='http://0.0.0.0:7777/sell',
                json={
                    "password": "123",
                    "mnemonic": wallet_info["mnemonic"],
                    "network": os.environ.get("NETWORK_NAME"),
                    "seller": wallet_info["address"],
                    "tokenId": wallet_info["token_id"],
                    "tokenAddress": os.environ.get("CONTRACT_ADDRESS"),
                    "startAmount": price / 10 ** 18
                }
            )

            print(response.text)
        else:
            log.warning(' --- Wallet with sufficient balance not found!')


class ListingsManager:
    def __init__(self, floor, step, orders, schema, strategy=None):
        self.floor = floor
        self.step = step
        self.orders = orders
        self.schema = schema
        self.strategy = strategy

    def filter(self, listings: list) -> list:
        self.strategy
        return listings

    def distribute(self) -> dict:
        _dist = {}
        _range = self.floor / 5

        _dist.update({-1: {'range': [0, self.floor], 'target': 0}})

        for i, j in enumerate(self.schema, 0):
            _dist.update({i: {
                'range': [round(self.floor + (_range * i), 3), round(self.floor + (_range * (i + 1)), 3)],
                'target': int(self.orders * (j / sum(self.schema)))
            }})

        return _dist

    def process(self, listings):
        listings = self.filter(listings)
        distribution = self.distribute()
        comparison = {}
        buy = []
        sell = []

        for _bin in distribution:
            _range = distribution[_bin]['range']
            _listings = listings.copy()
            comparison.update({_bin: {
                'target': distribution[_bin]['target'],
                'current': [],
                'range': _range
            }})
            for listing in _listings:
                if _range[0] <= listing['eth_price'] / (10 ** 18) <= _range[1]:
                    listings.pop(listings.index(listing))
                    comparison[_bin]['current'].append(listing)

        comparison = [comparison[i] for i in comparison]

        for _bin in comparison:
            if _bin['target'] > len(_bin['current']):
                sell.append({
                    'range': _bin['range'],
                    'amount': _bin['target'] - len(_bin['current'])
                })
            elif _bin['target'] < len(_bin['current']):
                buy += (random.sample(_bin['current'], len(_bin['current']) - _bin['target']))

        return buy, sell

    def move(self, init=False):
        if not init:
            self.floor *= self.step
            log.info(f'Target floor price: {self.floor} ETH')

        buy, sell = self.process(utils.get_opensea_listings())

        return buy, sell


class Orchestrator:
    def __init__(self, floor, step, orders, schema, period):
        self.listings = ListingsManager(
            floor=floor,
            step=step,
            orders=orders,
            schema=schema
        )

        log.info(f'Orchestrator has been started. Config:')
        log.info(f'Network: {os.environ.get("NETWORK_NAME")}')
        log.info(f'Contract: {os.environ.get("CONTRACT_ADDRESS")}')
        log.info(f'Initial floor price: {floor} ETH')
        log.info(f'Growth rate: {round((step - 1) * 100, 2)}% / {period} minutes')
        log.info(f'Active orders number: {orders}')

        self.wallets = WalletsManager(os.environ.get('MNEMONICS_PATH'))
        self.period = period

        wallets = self.wallets.wallets

        log.info(f'Available wallets number: {len(self.wallets.wallets)}')
        log.info(f'Balances:')

        eth_balance = sum([wallets[wallet]["eth_balance"] for wallet in wallets])
        log.info(f' --- {round(eth_balance / 10 ** 18, 2)} ETH')

        nft_balance = sum([len(wallets[wallet]["nft_balance"]) for wallet in wallets])
        log.info(f' --- {nft_balance} NFTs')

        free_nft_balance = sum([len(wallets[wallet]["free_nft_balance"]) for wallet in wallets])
        log.info(f' --- {free_nft_balance} free NFTs')

        log.warning(f'Sleeping for 30 seconds, look into config carefully')
        time.sleep(0)

    def next_step(self, init=False):
        log.info(f'Making {"next" if not init else "first"} step')

        if not init:
            self.wallets.get_balances()

        buy, sell = self.listings.move(init)

        log.info('Listings to buy:')
        for listing in buy:
            log.info(f' --- [{listing["owner"][:4]}..{listing["owner"][-4:]}]\'s '
                     f'NFT #{listing["token_id"]} for {round(listing["eth_price"] / 10 ** 18, 2)} ETH')
            self.wallets.buy(listing)

        self.wallets.get_balances()

        log.info('Ranges to sell:')
        for _range in sell:
            log.info(f' --- {_range["amount"]} NFT in range {_range["range"]} ETHs')

            amount = _range['amount']
            for i in range(amount):
                price = round(random.uniform(_range['range'][0], _range['range'][1]), 3) * (10 ** 18)
                self.wallets.sell(price)

        log.info(f'Sleeping for {self.period} minutes')
        time.sleep(self.period * 60)

    def start(self):
        self.next_step(True)

        while True:
            self.next_step()
