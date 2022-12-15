import os
import json
import sys
import time
import requests

from src.logger import log

from web3 import Web3

from settings import config

web3 = Web3(Web3.HTTPProvider(os.environ.get('WEB3_PROVIDER')))

with open(os.environ.get('CONTRACT_ABI_PATH'), 'r') as f:
    contract = web3.eth.contract(address=os.environ.get('CONTRACT_ADDRESS'), abi=json.load(f))


def shorten(data):
    if type(data) == int or data.isdigit():
        return round(float(data) / 10 ** 18, 2)

    return f'[{data[:4]}..{data[-4:]}]'


def get_address(mnemonic):
    web3.eth.account.enable_unaudited_hdwallet_features()
    account = web3.eth.account.from_mnemonic(mnemonic, account_path="m/44'/60'/0'/0/0")

    return account._key_obj


def get_addresses(mnemonics) -> dict:
    log.debug(f'Reading addresses from mnemonics...')

    addresses = {}
    for m in mnemonics:
        addresses.update({get_address(m): {'mnemonic': m}})

    log.debug(f'Recognised {len(addresses)} addresses')

    return addresses


def get_eth_balance(address) -> int:
    balance = web3.eth.get_balance(address)

    if shorten(balance):
        log.debug(f' --- [{shorten(address)}]\'s balance: {shorten(balance)} ETH')

    return balance


def get_nft_balance(address) -> dict:
    nft_balance = []
    for nft in range(contract.functions.balanceOf(address).call()):
        token_id = contract.functions.tokenOfOwnerByIndex(address, nft).call()
        nft_balance.append(token_id)

    if not nft_balance:
        return {
            'nft_balance': [],
            'free_nft_balance': []
        }

    if 0 in nft_balance:
        nft_balance.remove(0)

    log.debug(f' --- [{shorten(address)}]\'s NFTs: {nft_balance}')

    free_nft_balance = nft_balance.copy()
    ids = '&token_ids='.join([str(nft) for nft in nft_balance])

    response = requests.get(
        url=f'{os.environ.get("OPENSEA_LISTINGS_ENDPOINT")}' 
            f'?asset_contract_address={os.environ.get("CONTRACT_ADDRESS")}&token_ids={ids}&limit={len(nft_balance)}',
        headers={"Accept": "application/json"}
    ).json()
    time.sleep(0.5)

    for order in response['orders']:
        for asset in order['maker_asset_bundle']['assets']:
            free_nft_balance.remove(int(asset['token_id']))

    log.debug(f' --- [{shorten(address)}]\'s free NFTs: {free_nft_balance}')

    return {
        'nft_balance': nft_balance,
        'free_nft_balance': free_nft_balance
    }


def get_gas_price() -> int:
    return web3.eth.gas_price


def get_opensea_listings():
    total_supply = contract.functions.totalSupply().call()

    listings, result = [], []

    iterations = total_supply // 20 + (1 if total_supply % 20 > 0 else 0)
    for i in range(iterations):
        ids = '&token_ids='.join([str(i) for i in list(range(i * 20, (i + 1) * 20))])
        response = requests.get(
            url=f'{os.environ.get("OPENSEA_LISTINGS_ENDPOINT")}'
                f'?asset_contract_address={os.environ.get("CONTRACT_ADDRESS")}&token_ids={ids}&limit=50',
            headers={"Accept": "application/json"}
        ).json()

        if response.get('orders'):
            listings += response.get('orders')
        else:
            print(f'ERROR: {response}')
            sys.exit(1)

        time.sleep(0.5)

    for order in listings:
        price = 0
        for part in order['protocol_data']['parameters']['consideration']:
            price += int(part['startAmount'])

        token_id = order['maker_asset_bundle']['assets'][0]['token_id']
        owner = order['protocol_data']['parameters']['offerer']

        result.append({'token_id': token_id, 'eth_price': price, 'owner': owner})

    return result
