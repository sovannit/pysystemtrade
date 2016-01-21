"""
Algos.py

Basic building blocks of trading rules, like volatility measurement and crossovers

"""
import pandas as pd

from syscore.genutils import str2Bool
from systems.defaults import system_defaults


def robust_vol_calc(x, days=35, min_periods=10, vol_abs_min=0.0000000001, vol_floor=True,
                    floor_min_quant=0.05, floor_min_periods=100,
                    floor_days=500):
    """
    Robust exponential volatility calculation, assuming daily series of prices
    We apply an absolute minimum level of vol (absmin);
    and a volfloor based on lowest vol over recent history

    :param days: Number of days in lookback (*default* 35)
    :type days: int
    :param min_periods: The minimum number of observations (*default* 10)
    :type min_periods: int

    :param vol_abs_min: The size of absolute minimum (*default* =0.0000000001) 0.0= not used
    :type absmin: float or None

    :param vol_floor Apply a floor to volatility (*default* True)
    :type vol_floor: bool
    :param floor_min_quant: The quantile to use for volatility floor (eg 0.05 means we use 5% vol) (*default 0.05)
    :type floor_min_quant: float
    :param floor_days: The lookback for calculating volatility floor, in days (*default* 500)
    :type floor_days: int
    :param floor_min_periods: Minimum observations for floor - until reached floor is zero (*default* 100)
    :type floor_min_periods: int

    :returns: pd.DataFrame -- volatility measure


    """

    # Standard deviation will be nan for first 10 non nan values
    vol = pd.ewmstd(x, span=days, min_periods=min_periods)

    vol[vol < vol_abs_min] = vol_abs_min

    if vol_floor:
        # Find the rolling 5% quantile point to set as a minimum
        vol_min = pd.rolling_quantile(
            vol, floor_days, floor_min_quant, floor_min_periods)
        # set this to zero for the first value then propogate forward, ensures
        # we always have a value
        vol_min.set_value(vol_min.index[0], vol_min.columns[0], 0.0)
        vol_min = vol_min.ffill()

        # apply the vol floor
        vol_with_min = pd.concat([vol, vol_min], axis=1)
        vol_floored = vol_with_min.max(axis=1, skipna=False).to_frame()
    else:
        vol_floored = vol

    vol_floored.columns = ["vol"]
    return vol_floored


def forecast_scalar(xcross, window=250000, min_periods=500, backfill=True):
    """
    Work out the scaling factor for xcross such that T*x has an abs value of 10
    
    :param x: 
    :type x: pd.DataFrame 1xT
    
    :param span:
    :type span: int
    
    :param min_periods:
    
    
    :returns: pd.DataFrame 
    """
    backfill=str2Bool(backfill) ## in yaml will come in as text
    ##We don't allow this to be changed in config
    target_abs_forecast = system_defaults['average_absolute_forecast']

    ## Take CS average first
    ## we do this before we get the final TS average otherwise get jumps in scalar
    x=xcross.abs().median(axis=1).to_frame()
    
    ## now the TS 
    avg_abs_value=pd.rolling_mean(x, window=window, min_periods=min_periods)
    scaling_factor=target_abs_forecast/avg_abs_value

    scaling_factor.columns=['scale_factor']
    
    if backfill:
        scaling_factor=scaling_factor.fillna(method="bfill")

    return scaling_factor


def diversification_multiplier():
    """
    Given N assets with a correlation matrix of H and  weights W summing to 1, 
    the diversification multiplier will be 1 / [ ( W x H x WT ) 1/2 ]
    
    We start with a pre cleaned (returns indexed and differenced, fcasts ffilled) of TxN
    We take weekly slices from this, and calculate correlation matrices
    We calculate correlations annually
    
    """