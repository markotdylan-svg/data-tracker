"""The sources the tracker calls and the items it keeps from each.

Every item has a key that I define (item_id), so the same item lines up from
one day to the next even if the source renames it or changes its symbol.

    coingecko:<symbol>   a coin's market data from CoinGecko (USD)
    kraken:<symbol>      a coin's <symbol>/USD trading pair on the Kraken exchange
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Coin:
    symbol: str      # my key, lower case, e.g. "btc"
    name: str        # display name
    category: str    # my grouping, used as a filter on the site


# The coins tracked. Category is my own classification.
COINS = [
    Coin("btc", "Bitcoin", "Currency"),
    Coin("eth", "Ethereum", "Smart contract platform"),
    Coin("usdt", "Tether", "Stablecoin"),
    Coin("bnb", "BNB", "Exchange token"),
    Coin("usdc", "USDC", "Stablecoin"),
    Coin("xrp", "XRP", "Payments"),
    Coin("sol", "Solana", "Smart contract platform"),
    Coin("trx", "TRON", "Smart contract platform"),
    Coin("doge", "Dogecoin", "Meme"),
    Coin("link", "Chainlink", "DeFi"),
    Coin("ada", "Cardano", "Smart contract platform"),
    Coin("xlm", "Stellar", "Payments"),
    Coin("bch", "Bitcoin Cash", "Currency"),
    Coin("near", "NEAR Protocol", "Smart contract platform"),
    Coin("ltc", "Litecoin", "Currency"),
    Coin("avax", "Avalanche", "Smart contract platform"),
    Coin("uni", "Uniswap", "DeFi"),
    Coin("sui", "Sui", "Smart contract platform"),
    Coin("hbar", "Hedera", "Smart contract platform"),
    Coin("shib", "Shiba Inu", "Meme"),
    Coin("aave", "Aave", "DeFi"),
    Coin("dot", "Polkadot", "Smart contract platform"),
    Coin("atom", "Cosmos Hub", "Smart contract platform"),
]
COIN_BY_SYMBOL = {c.symbol: c for c in COINS}

# CoinGecko coin id -> my symbol. Only these ids are requested.
COINGECKO_IDS = {
    "bitcoin": "btc",
    "ethereum": "eth",
    "tether": "usdt",
    "binancecoin": "bnb",
    "usd-coin": "usdc",
    "ripple": "xrp",
    "solana": "sol",
    "tron": "trx",
    "dogecoin": "doge",
    "chainlink": "link",
    "cardano": "ada",
    "stellar": "xlm",
    "bitcoin-cash": "bch",
    "near": "near",
    "litecoin": "ltc",
    "avalanche-2": "avax",
    "uniswap": "uni",
    "sui": "sui",
    "hedera-hashgraph": "hbar",
    "shiba-inu": "shib",
    "aave": "aave",
    "polkadot": "dot",
    "cosmos": "atom",
}

# Kraken pair as requested -> (key Kraken uses in its reply, my symbol).
KRAKEN_PAIRS = {
    "XBTUSD": ("XXBTZUSD", "btc"),
    "ETHUSD": ("XETHZUSD", "eth"),
    "USDTZUSD": ("USDTZUSD", "usdt"),
    "USDCUSD": ("USDCUSD", "usdc"),
    "XRPUSD": ("XXRPZUSD", "xrp"),
    "SOLUSD": ("SOLUSD", "sol"),
    "TRXUSD": ("TRXUSD", "trx"),
    "XDGUSD": ("XDGUSD", "doge"),
    "LINKUSD": ("LINKUSD", "link"),
    "ADAUSD": ("ADAUSD", "ada"),
    "XLMUSD": ("XXLMZUSD", "xlm"),
    "BCHUSD": ("BCHUSD", "bch"),
    "LTCUSD": ("XLTCZUSD", "ltc"),
    "AVAXUSD": ("AVAXUSD", "avax"),
    "UNIUSD": ("UNIUSD", "uni"),
    "AAVEUSD": ("AAVEUSD", "aave"),
    "DOTUSD": ("DOTUSD", "dot"),
    "ATOMUSD": ("ATOMUSD", "atom"),
}


@dataclass(frozen=True)
class Source:
    name: str    # used in file names and the source column
    fmt: str     # format the source returns; the raw file is <name>.<fmt>.gz
    url: str


SOURCES = [
    Source(
        "coingecko",
        "json",
        "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
        f"&ids={','.join(COINGECKO_IDS)}&per_page=250&page=1&price_change_percentage=24h",
    ),
    Source(
        "kraken",
        "json",
        f"https://api.kraken.com/0/public/Ticker?pair={','.join(KRAKEN_PAIRS)}",
    ),
]
SOURCE_BY_NAME = {s.name: s for s in SOURCES}
