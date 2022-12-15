import os
import time
import json

from web3 import Web3
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from settings import config


class EtherscanParser:
    def __init__(self):
        from settings.texts import user_agent, accept

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument(f'accept={accept}')
        options.add_argument(f'user-agent={user_agent}')

        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        self.web3 = Web3(Web3.HTTPProvider(os.environ.get('WEB3_PROVIDER')))
        self.contract = self.web3.eth.contract(
            address=self.web3.toChecksumAddress(os.environ.get('CONTRACT_ADDRESS')),
            abi=json.load(open(os.environ.get('CONTRACT_ABI_PATH'), 'r'))
        )
        self.cache = []
        self.update_cache(True)

    def update_cache(self, initialization=False):
        self.browser.get(url=os.environ.get('ETHERSCAN_URL'))

        soup = BeautifulSoup(self.browser.page_source, 'html.parser')
        pages = 5
        # pages = int(soup.find_all('li', attrs={'class': 'page-item disabled'})[-1].text.split('of')[-1].strip())

        data = []
        finished = False
        cached_txs = [tx['tx_hash'] for tx in self.cache] if not initialization else []

        for i in range(pages):
            if not finished:
                self.browser.get(url=os.environ.get('ETHERSCAN_URL') + f'&p={i + 1}')
                soup = BeautifulSoup(self.browser.page_source, 'html.parser')
                transactions = soup.find('div', attrs={'id': 'paywall_mask'})
                rows = transactions.find_all('tr')

                for row in rows:
                    columns = row.find_all('td')
                    if columns:
                        tx_hash = columns[1].text

                        method = columns[2].span['data-original-title']
                        if method != 'Set Approval For All':
                            continue

                        block = int(columns[3].text)
                        sender = columns[6].a['href'].split('/')[-1]

                        if tx_hash in cached_txs:
                            print(f'found cached tx: {tx_hash} on page {i + 1}, index: {rows.index(row)}')
                            finished = True
                            break

                        data.append({'tx_hash': tx_hash,
                                     'method': method,
                                     'sender': sender,
                                     'block': block
                                     })

                time.sleep(1)

        print(f'received {len(data)} transactions')

        self.cache = data + self.cache

    def parse_token_ids(self):
        accounts = list(set([tx['sender'] for tx in self.cache]))
        token_ids = []

        for account in accounts:
            account = self.web3.toChecksumAddress(account)
            balance = self.contract.functions.balanceOf(account).call()
            tokens = []
            for i in range(balance):
                tokens.append(self.contract.functions.tokenOfOwnerByIndex(account, i).call())

            token_ids += tokens

        print(token_ids)
