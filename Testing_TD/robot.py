# import json
# import time as time_true
import pprint
# import pathlib
import pandas as pd

from datetime import time
from datetime import datetime
from datetime import timezone
from datetime import timedelta

from typing import List
from typing import Dict
from typing import Union
from typing import Optional

from trades import Trade
from portfolio import Portfolio

from stock_frame import StockFrame

from td.client import TDClient
from td.utils import milliseconds_since_epoch

 
class PyRobot():

    def __init__(self, client_id: str, redirect_uri: str, #paper_trading: bool = True, 
                credentials_path: Optional[str] = None, trading_account: Optional[str] = None) -> None:
        """Initalizes a new instance of the robot and logs into the API platform specified.

        Arguments:
        ----
        client_id {str} -- The Consumer ID assigned to you during the App registration. 
            This can be found at the app registration portal.

        redirect_uri {str} -- This is the redirect URL that you specified when you created your
            TD Ameritrade Application.

        Keyword Arguments:
        ----
        credentials_path {str} -- The path to the session state file used to prevent a full 
            OAuth workflow. (default: {None})

        trading_account {str} -- Your TD Ameritrade account number. (default: {None})

        """

        # Set the attirbutes
        self.trading_account = trading_account
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.credentials_path = credentials_path
        self.session: TDClient = self._create_session()
        self.trades = {}
        self.historical_prices = {}

        self.stock_frame:  None
        #self.stock_frame: StockFrame = None
        #self.paper_trading = paper_trading

        #self._bar_size = None
        #self._bar_type = None

    def _create_session(self) -> TDClient:
        """Start a new session.

        Creates a new session with the TD Ameritrade API and logs the user into
        the new session.

        Returns:
        ----
        TDClient -- A TDClient object with an authenticated sessions.

        """

        # Create a new instance of the client
        td_client = TDClient(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            credentials_path=self.credentials_path
        )

        # log the client into the new session
        td_client.login()

        return td_client

    @property
    def pre_market_open(self) -> bool:
        """Checks if pre-market is open.

        Uses the datetime module to create US Pre-Market Equity hours in
        UTC time.

        Usage:
        ----
            >>> trading_robot = PyRobot(
            client_id=CLIENT_ID, 
            redirect_uri=REDIRECT_URI, 
            credentials_path=CREDENTIALS_PATH
            )
            >>> pre_market_open_flag = trading_robot.pre_market_open
            >>> pre_market_open_flag
            True

        Returns:
        ----
        bool -- True if pre-market is open, False otherwise.

        """
        # UTC time NOT EST
        pre_market_start_time = datetime.utcnow().replace(
            hour=8,
            minute=00,
            second=00
        ).timestamp()

        market_start_time = datetime.utcnow().replace(
            hour=13,
            minute=30,
            second=00
        ).timestamp()

        right_now = datetime.utcnow().timestamp()

        if market_start_time >= right_now >= pre_market_start_time:
            return True
        else:
            return False

    @property
    def post_market_open(self):
        """Checks if post-market is open.

        Uses the datetime module to create US Post-Market Equity hours in
        UTC time.

        Usage:
        ----
            >>> trading_robot = PyRobot(
            client_id=CLIENT_ID, 
            redirect_uri=REDIRECT_URI, 
            credentials_path=CREDENTIALS_PATH
            )
            >>> post_market_open_flag = trading_robot.post_market_open
            >>> post_market_open_flag
            True

        Returns:
        ----
        bool -- True if post-market is open, False otherwise.

        """

        post_market_end_time = datetime.utcnow().replace(
            hour=00,
            minute=00,
            second=00
        ).timestamp()

        market_end_time = datetime.utcnow().replace(
            hour=20,
            minute=00,
            second=00
        ).timestamp()

        right_now = datetime.utcnow().timestamp()

        if post_market_end_time >= right_now >= market_end_time:
            return True
        else:
            return False

    @property
    def regular_market_open(self):
        """Checks if regular market is open.

        Uses the datetime module to create US Regular Market Equity hours in
        UTC time.

        Usage:
        ----
            >>> trading_robot = PyRobot(
            client_id=CLIENT_ID, 
            redirect_uri=REDIRECT_URI, 
            credentials_path=CREDENTIALS_PATH
            )
            >>> market_open_flag = trading_robot.market_open
            >>> market_open_flag
            True

        Returns:
        ----
        bool -- True if post-market is open, False otherwise.

        """

        market_start_time = datetime.utcnow().replace(
            hour=13,
            minute=30,
            second=00
        ).timestamp()

        market_end_time = datetime.utcnow().replace(
            hour=20,
            minute=00,
            second=00
        ).timestamp()

        right_now = datetime.utcnow().timestamp()

        if market_end_time >= right_now >= market_start_time:
            return True
        else:
            return False
    def create_portfolio(self) -> Portfolio:
        """Create a new portfolio.

        Creates a Portfolio Object to help store and organize positions
        as they are added and removed during trading.

        Usage:
        ----
            >>> trading_robot = PyRobot(
            client_id=CLIENT_ID, 
            redirect_uri=REDIRECT_URI, 
            credentials_path=CREDENTIALS_PATH
            )
            >>> portfolio = trading_robot.create_portfolio()
            >>> portfolio
            <pyrobot.portfolio.Portfolio object at 0x0392BF88>

        Returns:
        ----
        Portfolio -- A pyrobot.Portfolio object with no positions.
        """

        # Initalize the portfolio.
        self.portfolio = Portfolio(account_number=self.trading_account)

        # Assign the Client
        self.portfolio.td_client = self.session

        return self.portfolio

    def grab_current_quotes(self) -> dict:
        """Grabs the current quotes for all positions in the portfolio.

        Returns:
        ----
        dict -- A dictionary containing all the quotes for each position.

        """

        # First grab all the symbols.
        symbols = self.portfolio.positions.keys()

        # Grab the quotes.
        quotes = self.session.get_quotes(instruments=list(symbols))

        return quotes   

    def create_stock_frame(self, data: List[dict]) -> StockFrame:
        """Generates a new StockFrame Object.

        Arguments:
        ----
        data {List[dict]} -- The data to add to the StockFrame object.

        Returns:
        ----
        StockFrame -- A multi-index pandas data frame built for trading.
        """

        # Create the Frame.
        self.stock_frame = StockFrame(data=data)

        return self.stock_frame

    def grab_historical_prices(self, start: datetime, end: datetime, bar_size: int = 1,
                               bar_type: str = 'day', symbols: Optional[List[str]] = None) -> List[dict]:
        """Grabs the historical prices for all the postions in a portfolio.

        Overview:
        ----
        Any of the historical price data returned will include extended hours
        price data by default.

        Arguments:
        ----
        start {datetime} -- Defines the start date for the historical prices.

        end {datetime} -- Defines the end date for the historical prices.

        Keyword Arguments:
        ----
        bar_size {int} -- Defines the size of each bar. (default: {1})

        bar_type {str} -- Defines the bar type, can be one of the following:
            `['minute', 'week', 'month', 'year']` (default: {'minute'})

        symbols {List[str]} -- A list of ticker symbols to pull. (default: None)

        Returns:
        ----
        {List[Dict]} -- The historical price candles.

        Usage:
        ----
            >>> trading_robot = PyRobot(
                client_id=CLIENT_ID,
                redirect_uri=REDIRECT_URI,
                credentials_path=CREDENTIALS_PATH
                )
            >>> start_date = datetime.today()
            >>> end_date = start_date - timedelta(days=30)
            >>> historical_prices = trading_robot.grab_historical_prices(
                    start=end_date,
                    end=start_date,
                    bar_size=1,
                    bar_type='minute'
                )
        """

        self._bar_size = bar_size
        self._bar_type = bar_type

        start = str(milliseconds_since_epoch(dt_object=start))
        end = str(milliseconds_since_epoch(dt_object=end))

        new_prices = []

        if not symbols:
            symbols = self.portfolio.positions

        for symbol in symbols:

            historical_prices_response = self.session.get_price_history(
                symbol=symbol,
                period_type='day',
                start_date=start,
                end_date=end,
                frequency_type=bar_type,
                frequency=bar_size,
                extended_hours=True
            )

            self.historical_prices[symbol] = {}
            self.historical_prices[symbol]['candles'] = historical_prices_response['candles']

            for candle in historical_prices_response['candles']:

                new_price_mini_dict = {}
                new_price_mini_dict['symbol'] = symbol
                new_price_mini_dict['open'] = candle['open']
                new_price_mini_dict['close'] = candle['close']
                new_price_mini_dict['high'] = candle['high']
                new_price_mini_dict['low'] = candle['low']
                new_price_mini_dict['volume'] = candle['volume']
                new_price_mini_dict['datetime'] = candle['datetime']
                new_prices.append(new_price_mini_dict)

        self.historical_prices['aggregated'] = new_prices

        return self.historical_prices
         
    def create_trade(self, trade_id: str, enter_or_exit: str, long_or_short: str, order_type: str = 'mkt', price: float = 0.0, stop_limit_price=0.0) -> Trade:
        """Initalizes a new instance of a Trade Object.

        This helps simplify the process of building an order by using pre-built templates that can be
        easily modified to incorporate more complex strategies.

        Arguments:
        ----
        trade_id {str} -- The ID associated with the trade, this can then be used to access the trade during runtime.

        enter_or_exit {str} -- Defines whether this trade will be used to enter or exit a position.
            If used to enter, specify `enter`. If used to exit, speicfy `exit`.

        long_or_short {str} -- Defines whether this trade will be used to go long or short a position.
            If used to go long, specify `long`. If used to go short, speicfy `short`.

        Keyword Arguments:
        ----
        order_type {str} -- Defines the type of order to initalize. Possible values
            are `'mkt', 'lmt', 'stop', 'stop-lmt', 'trailign-stop'` (default: {'mkt'})

        price {float} -- The Price to be associate with the order. If the order type is `stop` or `stop-lmt` then 
            it is the stop price, if it is a `lmt` order then it is the limit price, and `mkt` is the market 
            price.(default: {0.0})

        stop_limit_price {float} -- Only used if the order is a `stop-lmt` and represents the limit price of
            the `stop-lmt` order. (default: {0.0})

        Usage:
        ----
            >>> trading_robot = PyRobot(
                client_id=CLIENT_ID, 
                redirect_uri=REDIRECT_URI, 
                credentials_path=CREDENTIALS_PATH
            )
            >>> new_trade = trading_robot_portfolio.create_trade(
                trade_id='long_1',
                enter_or_exit='enter',
                long_or_short='long',
                order_type='mkt'
            )
            >>> new_trade

            >>> new_market_trade = trading_robot_portfolio.create_trade(
                trade_id='long_2',
                enter_or_exit='enter',
                long_or_short='long',
                order_type='mkt',
                price=12.00
            )
            >>> new_market_trade

            >>> new_stop_trade = trading_robot_portfolio.create_trade(
                trade_id='long_3',
                enter_or_exit='enter',
                long_or_short='long',
                order_type='stop',
                price=2.00
            )
            >>> new_stop_trade

            >>> new_stop_limit_trade = trading_robot_portfolio.create_trade(
                trade_id='long_4',
                enter_or_exit='enter',
                long_or_short='long',
                order_type='stop-lmt',
                price=2.00,
                stop_limit_price=1.90
            )
            >>> new_stop_limit_trade

        Returns:
        ----
        Trade -- A pyrobot.Trade object with the specified template.
        """

        # Initalize a new trade object.
        trade = Trade()

        # Create a new trade.
        trade.new_trade(
            trade_id=trade_id,
            order_type=order_type,
            side=long_or_short,
            enter_or_exit=enter_or_exit,
            price=price,
            stop_limit_price=stop_limit_price
        )

        self.trades[trade_id] = trade

        return trade