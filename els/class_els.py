from els.gen_schedule import make_joint_calendar, schedule_generator
from idxdata.historical_data import get_hist_data_from_sql

import numpy as np
import pandas as pd
import QuantLib as ql

from datetime import date
from typing import List, Dict


class SimpleELS:
    def __init__(self,
                underlying: List,
                start_date: date,
                maturity: int,
                periods: int,
                coupon: float,
                barrier: List,
                df: pd.DataFrame = None,
                holiday: bool = True):

        self.underlying = underlying
        self.start_date = start_date
        self.maturity = maturity
        self.periods = periods
        self.coupon = coupon
        self.barrier = barrier
        self.holiday = holiday
        self.df = df

    def get_info(self) -> Dict:
        return {'underlying': self.underlying,
                'start_date': self.start_date,
                'maturity': self.maturity,
                'periods': self.periods,
                'coupon': self.coupon,
                'barrier': self.barrier}

    def get_calendar(self) -> ql.Calendar:
        return make_joint_calendar(self.underlying)

    def get_schedule(self) -> List:
        return schedule_generator(
            self.maturity,
            self.periods,
            self.start_date,
            self.get_calendar(),
            self.holiday
        )

    def get_initial_price(self) -> pd.DataFrame:
        df_initial_price = self.df.loc[self.start_date][self.underlying]
        return np.array(df_initial_price).reshape(1, len(self.underlying))

    def get_schedule_price(self) -> pd.DataFrame:
        return self.df.loc[self.get_schedule()][self.underlying]

    def get_ratio_price(self) -> pd.DataFrame:
        return self.get_schedule_price() / self.get_initial_price()

    def get_result(self) -> List:
        for i in range(len(self.barrier)):
            cond_KO = np.min(self.get_ratio_price().iloc[i]) > self.barrier[i]
            cond_loss = np.min(self.get_ratio_price().iloc[-1]) < self.barrier[-1]

            if cond_KO:
                return [
                    self.periods * (i + 1),
                    self.periods * (i + 1) * self.coupon / 12,
                    '??????'
                ]

            elif i == len(self.barrier) - 1 and cond_loss:
                return [
                    self.periods * (i + 1),
                    np.min(self.get_ratio_price().iloc[-1]) - 1,
                    '????????????'
                ]


# 3to1 ?????????
class Erase3To1ELS(SimpleELS):
    # ???????????? ?????? ??????.
    # moment = 2 --> 2?????? ???????????? 3to1
    def __init__(self,
                 underlying,
                 start_date,
                 maturity,
                 periods,
                 coupon,
                 barrier,
                 moment: int,
                 df=None,
                 holiday=True):

        super().__init__(underlying,
                         start_date,
                         maturity,
                         periods,
                         coupon,
                         barrier,
                         df,
                         holiday)

        self.moment = moment

    def get_info(self):
        return {'underlying': self.underlying,
                'start_date': self.start_date,
                'maturity': self.maturity,
                'periods': self.periods,
                'coupon': self.coupon,
                'barrier': self.barrier,
                'moment': self.moment}

    def get_ratio_3to1_price(self) -> pd.DataFrame:
        df_ratio = self.get_ratio_price()
        cond_worst = (df_ratio.iloc[self.moment - 1, :] == min(df_ratio.iloc[self.moment - 1]))
        worst_index = df_ratio.columns[cond_worst]
        df_ratio.iloc[self.moment:, :] = df_ratio[worst_index][self.moment:]
        return df_ratio

    def get_result(self):
        for i in range(len(self.barrier)):
            cond_KO = np.min(self.get_ratio_3to1_price().iloc[i]) > self.barrier[i]
            cond_loss = np.min(self.get_ratio_3to1_price().iloc[-1]) < self.barrier[-1]
            if cond_KO:
                return [
                    self.periods * (i + 1),
                    self.periods * (i + 1) * self.coupon / 12,
                    '??????'
                ]

            elif i == len(self.barrier) - 1 and cond_loss:
                return [
                    self.periods * (i + 1),
                    np.min(self.get_ratio_3to1_price().iloc[-1]) - 1,
                    '????????????'
                ]


# ??????
class KIELS(SimpleELS):
    def __init__(self,
                 underlying,
                 start_date,
                 maturity,
                 periods,
                 coupon,
                 barrier,
                 KI_barrier: float,
                 df=None,
                 holiday=True):

        super().__init__(underlying,
                         start_date,
                         maturity,
                         periods,
                         coupon,
                         barrier,
                         df,
                         holiday)

        self.KI_barrier = KI_barrier

    def get_info(self):
        return {'underlying': self.underlying,
                'start_date': self.start_date,
                'maturity': self.maturity,
                'periods': self.periods,
                'coupon': self.coupon,
                'barrier': self.barrier,
                'KI_barrier': self.KI_barrier}

    def get_result(self):
        df_total_period = self.df.loc[self.start_date:self.get_schedule()[-1]]
        df_total_ratio_price = df_total_period[self.underlying] / self.get_initial_price()
        worst_ratio = df_total_ratio_price.min(axis=1).min(axis=0)

        if worst_ratio >= self.KI_barrier:
            KI_hit = False
        else:
            KI_hit = True

        for i in range(len(self.barrier)):
            cond_KO = np.min(self.get_ratio_price().iloc[i]) > self.barrier[i]
            cond_loss = np.min(self.get_ratio_price().iloc[-1]) < self.barrier[-1]

            if cond_KO:
                return [
                    self.periods * (i + 1),
                    self.periods * (i + 1) * self.coupon / 12,
                    '??????'
                ]

            elif i == len(self.barrier) - 1 and cond_loss:

                if KI_hit:

                    return [
                        self.periods * (i + 1),
                        np.min(self.get_ratio_price().iloc[-1]) - 1,
                        'KI ????????????'
                    ]

                else:

                    return [
                        self.periods * (i + 1),
                        self.periods * (i + 1) * self.coupon / 12,
                        'No KI ????????????'
                    ]


class LizardELS(SimpleELS):
    """ Lizard??? dictionary ??????, ?????? ??????, 1???/2??? 90/85 ?????????????????? ?????? Lizard = {1:0.9, 2:0.85}
        Lizard coupon??? coupon??? ??????????????? default,  ?????? n ????????? Lizard_coupon??? n?????? """

    def __init__(self,
                 underlying,
                 start_date,
                 maturity,
                 periods,
                 coupon,
                 barrier,
                 Lizard: Dict,
                 Lizard_coupon: int = 1,
                 df=None,
                 holiday=True):

        super().__init__(underlying,
                         start_date,
                         maturity,
                         periods,
                         coupon,
                         barrier,
                         df,
                         holiday)

        self.Lizard = Lizard
        self.Lizard_coupon = Lizard_coupon

    def get_info(self):
        return {'underlying': self.underlying,
                'start_date': self.start_date,
                'maturity': self.maturity,
                'periods': self.periods,
                'coupon': self.coupon,
                'barrier': self.barrier,
                'Lizard': self.Lizard,
                'Lizard_coupon': self.Lizard_coupon}

    def get_Lizard_price(self) -> pd.DataFrame:
        index = np.array(list(self.Lizard.keys())) - 1
        lizard_price = self.get_schedule_price().iloc[index, :]
        return lizard_price

    def get_Lizard_ratio_price(self) -> pd.DataFrame:
        return self.get_Lizard_price()/self.get_initial_price()

    def get_result(self):
        for i in range(len(self.barrier)):
            cond_KO = np.min(self.get_ratio_price().iloc[i]) > self.barrier[i]
            cond_not_KO = np.min(self.get_ratio_price().iloc[i]) < self.barrier[i]
            if cond_KO:
                return [
                    self.periods * (i + 1),
                    self.periods * (i + 1) * self.coupon / 12,
                    '??????'
                ]

            elif cond_not_KO:
                cond_is_lizard = i in (np.array(list(self.Lizard.keys())) - 1)
                if cond_is_lizard and np.min(self.get_ratio_price().iloc[i]) > self.Lizard[i + 1]:
                    return [
                        self.periods * (i + 1),
                        self.periods * (i + 1) * self.Lizard_coupon * self.coupon / 12,
                       '???????????????'
                    ]

                elif i == len(self.barrier) - 1:
                    return [
                        self.periods * (i + 1),
                        np.min(self.get_ratio_price().iloc[i]) - 1,
                        '????????????'
                    ]


class LizardKIELS(LizardELS):
    def __init__(self,
                 underlying,
                 start_date,
                 maturity,
                 periods,
                 coupon,
                 barrier,
                 KI_barrier,
                 Lizard,
                 Lizard_coupon,
                 df=None,
                 holiday=True):

        super().__init__(underlying,
                         start_date,
                         maturity,
                         periods,
                         coupon,
                         barrier,
                         Lizard,
                         Lizard_coupon,
                         df,
                         holiday)

        self.KI_barrier = KI_barrier

    def get_info(self):
        return {'underlying': self.underlying,
                'start_date': self.start_date,
                'maturity': self.maturity,
                'periods': self.periods,
                'coupon': self.coupon,
                'barrier': self.barrier,
                'KI_barrier': self.KI_barrier,
                'Lizard': self.Lizard,
                'Lizard_coupon': self.Lizard_coupon}

    def get_result(self):
        df_total_period = self.df.loc[self.start_date:self.get_schedule()[-1]]
        df_total_ratio_price = df_total_period[self.underlying] / self.get_initial_price()
        worst_ratio = df_total_ratio_price.min(axis=1).min(axis=0)

        if worst_ratio >= self.KI_barrier:
            KI_hit = False
        else:
            KI_hit = True

        for i in range(len(self.barrier)):
            cond_KO = np.min(self.get_ratio_price().iloc[i]) > self.barrier[i]
            cond_not_KO = (np.min(self.get_ratio_price().iloc[i]) < self.barrier[i])
            if cond_KO:
                return [
                    self.periods * (i + 1),
                    self.periods * (i + 1) * self.coupon / 12,
                    '??????'
                ]

            elif cond_not_KO:
                cond_is_lizard = (i in np.array(list(self.Lizard.keys())) - 1)

                if cond_is_lizard and np.min(self.get_ratio_price().iloc[i]) > self.Lizard[i + 1]:
                    return [
                        self.periods * (i + 1),
                        self.periods * (i + 1) * self.Lizard_coupon * self.coupon / 12,
                        '???????????????'
                    ]

                elif i == len(self.barrier) - 1:
                    if KI_hit:
                        return [
                            self.periods * (i + 1),
                            np.min(self.get_ratio_price().iloc[i] - 1),
                            'KI ????????????'
                        ]

                    else:
                        return [
                            self.periods * (i + 1),
                            self.periods * (i + 1) * self.coupon / 12,
                            'No KI ????????????'
                        ]


class MPELS(SimpleELS):
    def __init__(self,
                 underlying,
                 start_date,
                 maturity,
                 periods,
                 coupon,
                 barrier,
                 MP_barrier: float,
                 df=None,
                 holiday=True):

        super().__init__(underlying,
                         start_date,
                         maturity,
                         periods,
                         coupon,
                         barrier,
                         df,
                         holiday)

        self.MP_barrier = MP_barrier

    def get_info(self):
        return {'underlying': self.underlying,
                'start_date' : self.start_date,
                'maturity' : self.maturity,
                'periods' : self.periods,
                'coupon' : self.coupon,
                'barrier' : self.barrier,
                'MP_barrier' : self.MP_barrier}

    def get_schedule(self):
        return schedule_generator(
            self.maturity,
            1,
            self.start_date,
            self.get_calendar(),
            self.holiday
        )

    def MP_barrier_list(self) -> List:
        MP_barrier_list = np.ones(self.maturity * 12) * self.MP_barrier

        for i, v in enumerate(self.barrier):
            MP_barrier_list[(i + 1) * self.periods - 1] = v

        return MP_barrier_list

    def get_result(self):
        cum_coupon = 0
        num = 0

        for i, v in enumerate(self.MP_barrier_list()):
            # ?????? ?????? ??????????????? ??????
            cond_MP = np.min(self.get_ratio_price().iloc[i]) > self.MP_barrier
            if cond_MP:
                num += 1
                cum_coupon += self.coupon / 12

            if i % self.periods == self.periods - 1:
                # ?????? ??????????????? ??????
                if i != len(self.MP_barrier_list()) - 1: # ??????????????? ?????????
                    # ??????????????? ???????????? ??????
                    if np.min(self.get_ratio_price().iloc[i]) > v:
                        return [
                            i + 1,
                            cum_coupon,
                            f'??????({num})'
                        ]

                else:    # ?????? ???????????????
                    # ???????????? ???????????? ????????????
                    if np.min(self.get_ratio_price().iloc[i]) > v:
                        return [
                            i + 1,
                            cum_coupon,
                            f'????????????({num})'
                        ]
                    # ?????????????????? ????????????, ?????? ????????? ?????? ???????????? ???????????? + ????????????
                    else:
                        return [
                            i + 1,
                            np.min(self.get_ratio_price().iloc[-1]) - 1 + cum_coupon,
                            f'????????????({num})'
                        ]


if __name__ == "__main__":

    # ELS ??????
    underlying = ["HSCEI", 'EUROSTOXX50', 'KOSPI200']
    start_date = date(2018, 1, 1)
    maturity = 3  # ??????(??????:???)
    periods = 6  # ??????(??????:???)
    coupon = 0.05
    barrier = [0.95, 0.90, 0.80, 0.75, 0.70, 0.60]
    KI_barrier = 0.5
    Lizard = {1: 0.90, 2: 0.85}
    MP_barrier = 0.6
    df = get_hist_data_from_sql(date(2001, 1, 1), date.today(), underlying, type='w')

    #ELS ??????
    els1 = SimpleELS(underlying, start_date, maturity, periods, coupon, barrier, df)
    els2 = Erase3To1ELS(underlying, start_date, maturity, periods, coupon, barrier, 2, df)
    els3 = KIELS(underlying, start_date, maturity, periods, coupon, barrier, KI_barrier, df)
    els4 = LizardELS(underlying, start_date, maturity, periods, coupon, barrier, Lizard, 1, df)
    els5 = LizardKIELS(underlying, start_date, maturity, periods, coupon, barrier, KI_barrier, Lizard, 1, df)
    els6 = MPELS(underlying, start_date, maturity, periods, coupon, barrier, MP_barrier, df, holiday=True)
    els7 = MPELS(underlying, start_date, maturity, periods, coupon, barrier, MP_barrier, df, holiday=False)

    print(els7.get_result())
