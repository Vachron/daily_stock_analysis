from data_provider.base import DataFetcherManager


class DataProviderFactory(DataFetcherManager):

    def get_daily_history(self, stock_code, start_date=None, end_date=None, days=120,
                          adjust="qfq"):
        if start_date is not None:
            start_str = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
        else:
            start_str = None
        if end_date is not None:
            end_str = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)
        else:
            end_str = None

        try:
            df, _source = self.get_daily_data(
                stock_code,
                start_date=start_str,
                end_date=end_str,
                days=days,
                adjust=adjust,
            )
            return df
        except Exception:
            return None
