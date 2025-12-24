"""
加工時間の算出式をまとめたファイル

Notes:
    有効数字は小数第2位まで
"""

import math
from decimal import Decimal, ROUND_HALF_UP


# --- 定数 ---
SPECIFIC_GRAVITY_OF_IRON: float = 7.85  # 鉄の比重


def calc_weight(thickness: float, width: float, length: float) -> float:
    """
    単重量を算出する関数

    Args:
        thickness: 板厚 [mm]
        width: 幅 [mm]
        length: 長さ [mm]

    Returns:
        weight: 単重量 [kg]（小数第2位を四捨五入）
    """
    weight = thickness * width * length * SPECIFIC_GRAVITY_OF_IRON * 0.000001
    return round(weight, 1)


def calc_removal_time(weight: float, is_parallel_shapes: bool) -> float:
    """
    脱着時間を算出する関数

    Args:
        weight: 重量（kg）
        is_parallel_shapes: 平行な形状かどうか

    Returns:
        removal_time: 脱着時間

    Notes:
        重量が15kgかどうかと平行な形状であるかどうかを判定する。
    """
    if weight < 15:
        if is_parallel_shapes:
            removal_time = 0.5
        else:
            removal_time = 0.75
    else:
        if is_parallel_shapes:
            removal_time = 1.2
        else:
            removal_time = 3.5
    return removal_time


class CheckCompatibleMachines:
    """
    対応可能な機械をチェックするクラス

    Attributes:
        _is_parallel_shapes: 平行な形状かどうか
        _thickness: 板厚 [mm]
        _width: 幅 [mm]
        _length: 長さ [mm]
        _max_tool_length: 最大工具長 [mm]
        can_process_M1_X: M1-?号機が対応可能かどうか
    """

    # --- 各号機のサイズ ---
    M1_1_SIZE: dict = {
        "vise": {"height": 180, "width": 410},  # バイス
        "table": {"width": 650, "length": 2000},  # テーブル
        "max_height": 760,  # 最大高さ
    }
    """M1-1号機ので加工するときに必要なサイズ"""

    M1_2_SIZE: dict = {
        "vise": {"height": 155, "width": 350},  # バイス
        "table": {"width": 500, "length": 1000},  # テーブル
        "max_height": 670,  # 最大高さ
    }
    """M1-2号機ので加工するときに必要なサイズ"""

    M1_3_SIZE: dict = {
        "vise": {"height": 180, "width": 410},  # バイス
        "table": {"width": 800, "length": 2000},  # テーブル
        "max_height": 850,  # 最大高さ
    }
    """M1-3号機ので加工するときに必要なサイズ"""

    M1_4_SIZE: dict = {
        "vise": {"height": 155, "width": 270},  # バイス
        "table": {"width": 500, "length": 1000},  # テーブル
        "max_height": 670,  # 最大高さ
    }
    """M1-4号機ので加工するときに必要なサイズ"""

    M1_7_SIZE: dict = {
        "vise": {"height": 180, "width": 410},  # バイス
        "table": {"width": 800, "length": 2000},  # テーブル
        "max_height": 850,  # 最大高さ
    }
    """M1-7号機ので加工するときに必要なサイズ"""

    def __init__(
        self,
        is_parallel_shapes: bool,
        thickness: float,
        width: float,
        length: float,
        max_tool_length: float,
    ):
        self._is_parallel_shapes = is_parallel_shapes
        self._thickness = thickness
        self._width = width
        self._length = length
        self._max_tool_length = max_tool_length

        # --- 対応判定 ---
        ## M1-1, 4はバイスのみ
        self.can_process_M1_1 = self._check_machine_use_only_vise(
            machine_size=self.M1_1_SIZE
        )
        self.can_process_M1_4 = self._check_machine_use_only_vise(
            machine_size=self.M1_4_SIZE
        )
        ## M1-2, 3, 7はバイスとクランプ
        self.can_process_M1_2 = self._check_machine_use_vise_and_clamp(
            machine_size=self.M1_2_SIZE
        )
        self.can_process_M1_3 = self._check_machine_use_vise_and_clamp(
            machine_size=self.M1_3_SIZE
        )
        self.can_process_M1_7 = self._check_machine_use_vise_and_clamp(
            machine_size=self.M1_7_SIZE
        )

    def _check_fit_in_width(self, width: float) -> bool:
        """
        製品の幅が収まるかをチェックするメソッド

        Args:
            width: 比べる幅
        """
        return self._width < width

    def _check_fit_in_length(self, length: float) -> bool:
        """
        製品の長さが収まるかをチェックするメソッド

        Args:
            length: 比べる長さ
        """
        return self._length < length

    def _check_fit_in_vise_by_height(
        self, max_height: float, vise_height: float
    ) -> bool:
        """
        製品の高さがバイスの高さに収まるかをチェックするメソッド

        Args:
            max_height: 最大高さ
            vise_height: バイスの長さ
        """
        return max_height - (vise_height + self._max_tool_length + self._thickness) > 10

    def _check_machine_use_only_vise(self, machine_size: dict) -> bool:
        """
        バイスのみを使用する機械で対応可能かをチェックするメソッド

        Args:
            machine_size: 機械で加工するときに必要なサイズ

        Notes:
            M1-1号機とM1-4号機が該当
        """
        if not self._is_parallel_shapes:
            return False
        return all(
            [
                self._check_fit_in_width(width=machine_size["vise"]["width"]),
                self._check_fit_in_length(length=machine_size["table"]["length"]),
                self._check_fit_in_vise_by_height(
                    max_height=machine_size["max_height"],
                    vise_height=machine_size["vise"]["height"],
                ),
            ]
        )

    def _check_fit_in_clamp_by_height(self, max_height: float) -> bool:
        """
        製品の高さがクランプの高さに収まるかをチェックするメソッド

        Args:
            max_height: 最大高さ
        """
        return max_height - (self._max_tool_length + self._thickness + 20) > 10

    def _check_machine_use_vise_and_clamp(self, machine_size: dict) -> bool:
        """
        バイスとクランプを使用する機械で対応可能かをチェックするメソッド

        Args:
            machine_size: 機械で加工するときに必要なサイズ

        Returns
            can_process: 対応可能かどうかをbool型で示す変数

        Notes:
            M1-2号機とM1-3号機とM1-7号機が該当
        """
        # ---形状が平行でなければ抑え金のみ ---
        if not self._is_parallel_shapes:
            if all(
                [
                    self._check_fit_in_width(width=machine_size["table"]["width"]),
                    self._check_fit_in_length(length=machine_size["table"]["length"]),
                    self._check_fit_in_clamp_by_height(
                        max_height=machine_size["max_height"],
                    ),
                ]
            ):
                return True
        # --- 形状が平行であればバイスの確認をしてから抑え金を確認 ---
        return all(
            [
                self._check_fit_in_width(machine_size["table"]["width"]),
                self._check_fit_in_length(machine_size["table"]["length"]),
                self._check_fit_in_clamp_by_height(machine_size["max_height"]),
            ]
        )


def calc_rpm(surface_speed: float, diameter: float) -> float:
    """
    回転数を算出する関数

    Args:
        surface_speed: 周速 [m/min]
        diameter: 工具径 [mm]

    Returns:
        revolutions_per_minute: 回転数 [rpm]
    """
    revolutions_per_minute = (1000 * surface_speed) / (math.pi * diameter)
    return revolutions_per_minute


def calc_feed_speed(feed: float, rpm: float) -> float:
    """
    送り速度を算出する関数

    Args:
        feed: 送り [mm/rev]
        rpm: 回転数 [rpm]

    Returns:
        feed_speed: [mm/min]
    """
    feed_speed = feed * rpm
    return feed_speed

def calc_num_cutting_depths(depth: float, cutting_depth: float) -> float:
    """
    Z回数を算出する関数 ※切り上げ

    Args:
        depth: 深さ [mm]
        cutting_depth: 切り込み量 [mm]

    Returns:
        num_cutting_depths
    """
    num_cutting_depths = depth / cutting_depth
    return math.ceil(num_cutting_depths)


def rounding_two_decimal(value: float) -> Decimal:
    """
    小数値を四捨五入して小数第2位までに丸める関数

    Args
        value: 丸めたい値

    Returns
        rounded_value: 小数第2位まで四捨五入された値
    """
    rounded_value = Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return rounded_value


class Drill:
    """
    ドリル加工を条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        diameter: float,
        surface_speed: float,
        depth: float,
        feed: float,
        num_holes: int,
    ):
        """
        Args:
            diameter: ドリル径 [mm]
            surface_speed: 周速 [m/min]
            depth: 加工深さ [mm]
            feed: 送り [mm/rev]
            num_holes: 穴数
        """
        self._diameter = diameter
        self._surface_speed = surface_speed
        self._depth = depth
        self._feed = feed
        self._num_holes = num_holes

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        revolutions_per_minute = calc_rpm(
            surface_speed=self._surface_speed, diameter=self._diameter
        )
        feed_speed = calc_feed_speed(feed=self._feed, rpm=revolutions_per_minute)
        processing_time_min = ((self._depth / feed_speed) * 2) * self._num_holes

        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 20 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長) [min]
        """
        long_setup_time = 244 + self._num_holes * 30
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短) [min]
        """
        short_setup_time = 244 + self._num_holes * 20
        return short_setup_time


class Tap(Drill):
    """
    タップ加工を条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        diameter,
        surface_speed,
        depth,
        feed,
        num_holes,
        pilot_diameter: float,
        pilot_surface_speed: float,
        pilot_feed: float,
    ):
        """
        Args:
            diameter: タップ径 [mm]
            surface_speed: 周速 [m/min]
            depth: 加工深さ [mm]
            feed: 送り [mm/rev]
            num_holes: 穴数
            pilot_diameter: 下穴径 [mm]
            pilot_surface_speed: 下穴の周速 [m/min]
            pilot_feed: 下穴の送り [mm/rev]
        """
        self._diameter = diameter
        self._surface_speed = surface_speed
        self._depth = depth
        self._feed = feed
        self._num_holes = num_holes

        # --- 加工時間の算出 ---
        ## タップのみ
        tap_processing_time_min = self._calc_processing_time()
        ## 下穴
        self._diameter = pilot_diameter
        self._surface_speed = pilot_surface_speed
        self._feed = pilot_feed
        pilot_processing_time_min = self._calc_processing_time()
        ## 合算
        self.processing_time_min = tap_processing_time_min + pilot_processing_time_min
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 40 + self._num_holes * 15
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長) [min]
        """
        long_setup_time = 366 + self._num_holes * 30
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短) [min]
        """
        short_setup_time = 150 + self._num_holes * 20
        return short_setup_time
    
class PerfectCircleEndMill:
    """
    エンドミルの真円を条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        pilot_hole: 下穴径 [mm]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        diameter: float,
        num_holes: int,
        depth: float,
        cutting_depth: float,
        tool_diameter: float,
        surface_speed: float,
        feed: float,
        cutting_allowance: float,
    ):
        """
        Args:
            diameter: 加工径 [mm]
            num_holes: 穴数
            depth: 深さ [mm]
            cutting_depth: 切り込み量 [mm]
            tool_diameter: 工具径 [mm]
            surface_speed: 周速 [m/min]
            depth: 加工深さ [mm]
            feed: 送り [mm/rev]
            cutting_allowance: 取り代 [mm]
        """
        self._diameter = diameter
        self._num_holes = num_holes
        self._depth = depth
        self._cutting_depth = cutting_depth
        self._tool_diameter = tool_diameter
        self._surface_speed = surface_speed
        self._feed = feed
        self._cutting_allowance = cutting_allowance

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.pilot_hole = self._calc_pilot_hole()
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_cutting_length(self) -> float:
        """
        切削長を算出するメソッド

        Returns:
            cutting_length: 切削長 [mm]
        """
        cutting_length = self._diameter * math.pi * self._num_holes
        return cutting_length
    
    def _calc_pilot_hole(self) -> float:
        """
        下穴径を算出するメソッド

        Returns:
            pilot_hole: 下穴径 [mm]
        """
        pilot_hole = (self._diameter - (self._cutting_allowance) * 2)
        return pilot_hole

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        revolutions_per_minute = calc_rpm(
            surface_speed=self._surface_speed, diameter=self._tool_diameter
        )
        feed_speed = calc_feed_speed(feed=self._feed, rpm=revolutions_per_minute)
        cutting_length = self._calc_cutting_length()
        num_cutting_depths = calc_num_cutting_depths(
            depth=self._depth, cutting_depth=self._cutting_depth
        )
        processing_time_min = (cutting_length * num_cutting_depths) / feed_speed
        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 10 + self._num_holes * 3
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 265 + self._num_holes * 40
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 165 + self._num_holes * 40
        return short_setup_time


class SideEndMill:
    """
    エンドミルの側面を条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        cutting_length: 切削長 [mm]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        depth: float,
        cutting_depth: float,
        tool_diameter: float,
        surface_speed: float,
        feed: float,
        cutting_length: float,
    ):
        """
        Args:
            depth: 深さ [mm]
            cutting_depth: 切り込み量 [mm]
            tool_diameter: 工具径 [mm]
            surface_speed: 周速 [m/min]
            depth: 加工深さ [mm]
            feed: 送り [mm/rev]
            cutting_length: 切削長 [mm]
        """
        self._depth = depth
        self._cutting_depth = cutting_depth
        self._tool_diameter = tool_diameter
        self._surface_speed = surface_speed
        self._feed = feed
        self.cutting_length = cutting_length

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        revolutions_per_minute = calc_rpm(
            surface_speed=self._surface_speed, diameter=self._tool_diameter
        )
        feed_speed = calc_feed_speed(feed=self._feed, rpm=revolutions_per_minute)
        num_cutting_depths = calc_num_cutting_depths(
            depth=self._depth, cutting_depth=self._cutting_depth
        )
        processing_time_min = (
            (self.cutting_length * num_cutting_depths) / feed_speed
        ) * 1.25
        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 10
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 285
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 165
        return short_setup_time


class LongHoleEndMill:
    """
    エンドミルの長穴を条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        cutting_length: 切削長 [mm]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        width: float,
        length: float,
        num_holes: int,
        depth: float,
        cutting_depth: float,
        tool_diameter: float,
        surface_speed: float,
        feed: float,
    ):
        """
        Args:
            width: 幅 [mmm]
            length: 長さ [mm]
            num_holes: 穴数
            depth: 深さ [mm]
            cutting_depth: 切り込み量 [mm]
            tool_diameter: 工具径 [mm]
            surface_speed: 周速 [m/min]
            depth: 加工深さ [mm]
            feed: 送り [mm/rev]
        """
        self._width = width
        self._length = length
        self._num_holes = num_holes
        self._depth = depth
        self._cutting_depth = cutting_depth
        self._tool_diameter = tool_diameter
        self._surface_speed = surface_speed
        self._feed = feed

        # --- 加工時間の算出 ---
        self.cutting_length = self._calc_cutting_length() # 加工時間を算出するために先に計算
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)
        self.cutting_length = round(self.cutting_length, 2) # 丸め

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_cutting_length(self) -> float:
        """
        切削長を算出するメソッド

        Returns:
            cutting_length: 切削長 [mm]
        """
        cutting_length = (
            (self._width * math.pi) + (self._length * 2)
        ) * self._num_holes
        return cutting_length

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        revolutions_per_minute = calc_rpm(
            surface_speed=self._surface_speed, diameter=self._tool_diameter
        )
        feed_speed = calc_feed_speed(feed=self._feed, rpm=revolutions_per_minute)
        cutting_length = self._calc_cutting_length()
        num_cutting_depths = calc_num_cutting_depths(
            depth=self._depth, cutting_depth=self._cutting_depth
        )
        processing_time_min = ((self.cutting_length * num_cutting_depths) / feed_speed) * 1.3
        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 30 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 389 + self._num_holes * 30
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 269 + self._num_holes * 30
        return short_setup_time
    
class Boring:
    """
    ボーリングを条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        pilot_diameter: 下穴径 [mm]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        welded_hole: float,
        boring_diameter: float,
        boring_surface_speed: float,
        depth: float,
        boring_feed: float,
        num_holes: int,
        cutting_depth: float,
        endmill_tool_diameter: float,
        endmill_surface_speed: float,
        endmill_feed: float,
        cutting_allowance: float,
        drill_diameter: float = None,
        drill_surface_speed: float = None,
        drill_feed: float = None,
    ):
        """
        Args:
            welded_hole: 溶断孔 [mm]
            boring_diameter: ボーリングの加工径 [mm],
            boring_surface_speed: ボーリングの周速 [m/mim],
            depth: 深さ [mm],
            boring_feed: ボーリングの送り [mm/rev],
            num_holes: 穴数,
            cutting_depth: 切り込み量 [mm],
            endmill_tool_diameter: エンドミルの工具径,
            endmill_surface_speed: エンドミルの周速,
            endmill_feed: エンドミルの送り,
            cutting_allowance: 取り代 [mm],
            drill_diameter: ドリルの加工径（初期値None）
            drill_surface_speed: ドリルの周速（初期値None）
            drill_feed: ドリルの送り（初期値None）
        """
        self._welded_hole = welded_hole
        self._boring_diameter = boring_diameter
        self._boring_surface_speed = boring_surface_speed
        self._depth = depth
        self._boring_feed = boring_feed
        self._num_holes = num_holes
        self._cutting_depth = cutting_depth
        self._endmill_tool_diameter = endmill_tool_diameter
        self._endmill_surface_speed = endmill_surface_speed
        self._endmill_feed = endmill_feed
        self._cutting_allowance = cutting_allowance
        self._drill_diameter = drill_diameter
        self._drill_surface_speed = drill_surface_speed
        self._drill_feed = drill_feed

        # --- 加工時間の算出 ---
        self.pilot_diameter = (
            self._calc_pilot_diameter()
        )  # エンドミルの計算で使用するので先に計算
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_pilot_diameter(self) -> float:
        """
        下穴径を算出するメソッド

        Returns:
            pilot_diameter: 下穴径
        """
        if self._welded_hole != 0:
            pilot_diameter = self._boring_diameter - 0.2
        else:
            pilot_diameter = self._drill_diameter
        return pilot_diameter

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        # --- 下穴のドリルの加工時間の算出 ---
        if self._welded_hole != 0:
            drill_processing_time_min = 0
        else:
            drill = Drill(
                diameter=self._drill_diameter,
                surface_speed=self._drill_surface_speed,
                depth=self._depth,
                feed=self._drill_feed,
                num_holes=self._num_holes,
            )
            drill_processing_time_min = drill._calc_processing_time()

        # --- ボーリング単体の加工時間の算出 ---
        boring = Drill(
            diameter=self._boring_diameter,
            surface_speed=self._boring_surface_speed,
            depth=self._depth,
            feed=self._boring_feed,
            num_holes=self._num_holes,
        )
        boring_processing_time_min = boring._calc_processing_time()

        # --- ボーリングの下穴のエンドミルの加工時間の算出 ---
        class ForBoringEndmill(PerfectCircleEndMill):
            def _calc_cutting_length(self):
                """
                切削長を算出するメソッド

                Returns
                    cutting_length: 切削長 [mm]
                """
                cutting_length = self._diameter * math.pi
                return cutting_length

        endmill = ForBoringEndmill(
            diameter=self.pilot_diameter,
            num_holes=self._num_holes,
            depth=self._depth,
            cutting_depth=self._cutting_depth,
            tool_diameter=self._endmill_tool_diameter,
            surface_speed=self._endmill_surface_speed,
            feed=self._endmill_feed,
            cutting_allowance=self._cutting_allowance,
        )

        endmill_processing_time_min = endmill._calc_processing_time()

        # --- 合算 ---
        processing_time_min = (
            drill_processing_time_min
            + boring_processing_time_min
            + endmill_processing_time_min
        )

        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 40 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 809 + self._num_holes * 60
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 689 + self._num_holes * 60
        return short_setup_time

class Reamer:
    """
    リーマを条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        reamer_diameter: float,
        reamer_surface_speed: float,
        reamer_feed: float,
        depth: float,
        num_holes: int,
        pilot_diameter: float,
        cutting_depth: float,
        endmill_tool_diameter: float,
        endmill_surface_speed: float,
        endmill_feed: float,
        cutting_allowance: float,
        drill_diameter: float,
        drill_surface_speed: float,
        drill_feed: float,
    ):
        """
        Args:
            reamer_diameter: リーマの加工径 [mm],
            reamer_surface_speed: リーマの周速 [m/mim],
            reamer_feed: リーマの送り [mm/rev],
            depth: 深さ [mm],
            num_holes: 穴数,
            pilot_diameter: 下穴径 [mm]
            cutting_depth: 切り込み量 [mm],
            endmill_tool_diameter: エンドミルの工具径,
            endmill_surface_speed: エンドミルの周速,
            endmill_feed: エンドミルの送り,
            cutting_allowance: 取り代 [mm],
            drill_diameter: ドリルの加工径（初期値None）
            drill_surface_speed: ドリルの周速（初期値None）
            drill_feed: ドリルの送り（初期値None）
        """
        self._reamer_diameter = reamer_diameter
        self._reamer_surface_speed = reamer_surface_speed
        self._reamer_feed = reamer_feed
        self._depth = depth
        self._num_holes = num_holes
        self._pilot_diameter = pilot_diameter
        self._cutting_depth = cutting_depth
        self._endmill_tool_diameter = endmill_tool_diameter
        self._endmill_surface_speed = endmill_surface_speed
        self._endmill_feed = endmill_feed
        self._cutting_allowance = cutting_allowance
        self._drill_diameter = drill_diameter
        self._drill_surface_speed = drill_surface_speed
        self._drill_feed = drill_feed

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        # --- 下穴のドリルの加工時間の算出 ---
        drill = Drill(
            diameter=self._drill_diameter,
            surface_speed=self._drill_surface_speed,
            depth=self._depth,
            feed=self._drill_feed,
            num_holes=self._num_holes,
        )
        drill_processing_time_min = drill._calc_processing_time()

        # --- ボーリング単体の加工時間の算出 ---
        reamer = Drill(
            diameter=self._reamer_diameter,
            surface_speed=self._reamer_surface_speed,
            depth=self._depth,
            feed=self._reamer_feed,
            num_holes=self._num_holes,
        )
        reamer_processing_time_min = reamer._calc_processing_time()

        # --- ボーリングの下穴のエンドミルの加工時間の算出 ---
        class ForBoringEndmill(PerfectCircleEndMill):
            def _calc_cutting_length(self):
                """
                切削長を算出するメソッド

                Returns
                    cutting_length: 切削長 [mm]
                """
                cutting_length = self._diameter * math.pi
                return cutting_length

        endmill = ForBoringEndmill(
            diameter=self._pilot_diameter,
            num_holes=self._num_holes,
            depth=self._depth,
            cutting_depth=self._cutting_depth,
            tool_diameter=self._endmill_tool_diameter,
            surface_speed=self._endmill_surface_speed,
            feed=self._endmill_feed,
            cutting_allowance=self._cutting_allowance,
        )

        endmill_processing_time_min = endmill._calc_processing_time()

        # --- 合算 ---
        processing_time_min = (
            drill_processing_time_min
            + reamer_processing_time_min
            + endmill_processing_time_min
        )

        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 40 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 547 + self._num_holes * 60
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 427 + self._num_holes * 60
        return short_setup_time
    
class Counterbore:
    """
    ザグリを条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        counterbore_diameter: float,
        counterbore_depth: float,
        drill_diameter: float,
        depth: float,
        num_holes: float,
        cutting_depth: float,
        provisional_endmill_tool_diameter: float,
        endmill_tool_diameter: float,
        endmill_surface_speed: float,
        endmill_feed: float,
        drill_surface_speed: float,
        drill_feed: float,
        cutting_allowance: float=0,
    ):
        """
        Args:
            counterbore_diameter: ザグリ径 [mm]
            counterbore_depth: ザグリ深さ [mm]
            drill_diameter: 穴径 [mm]（ドリルの加工径）
            depth: 深さ [mm]
            num_holes: 穴数
            provisional_endmill_tool_diameter: 仮エンドミルの工具径 [mm]
            endmill_tool_diameter: エンドミルの工具径 [mm]
            endmill_surface_speed: エンドミルの周速 [m/min]
            endmill_feed: エンドミルの送り [mm/rev]
            cutting_depth: 切り込み量 [mm]
            drill_surface_speed: ドリルの周速 [m/min]
            drill_feed: ドリルの送り [mm/rev]
            cutting_allowance: 取り代 [mm]（実際には使用しないので初期値0で置いておく）
        """
        self._counterbore_diameter = counterbore_diameter
        self._counterbore_depth = counterbore_depth
        self._drill_diameter = drill_diameter
        self._depth = depth
        self._num_holes = num_holes
        self._provisional_endmill_tool_diameter = provisional_endmill_tool_diameter
        self._endmill_tool_diameter = endmill_tool_diameter
        self._endmill_surface_speed = endmill_surface_speed
        self._endmill_feed = endmill_feed
        self._cutting_depth = cutting_depth
        self._cutting_allowance = cutting_allowance
        self._drill_surface_speed = drill_surface_speed
        self._drill_feed = drill_feed

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_cutting_length(self):
        """
        切削長を算出するメソッド

        Returns
            cutting_length: 切削長 [mm]
        """
        cutting_length = (math.pi / 4) * (self._counterbore_diameter**2 - self._drill_diameter**2) / (self._provisional_endmill_tool_diameter * 0.5)
        return cutting_length

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        # --- 下穴のドリルの加工時間の算出 ---
        drill = Drill(
            diameter=self._drill_diameter,
            surface_speed=self._drill_surface_speed,
            depth=self._depth,
            feed=self._drill_feed,
            num_holes=self._num_holes,
        )
        drill_processing_time_min = drill._calc_processing_time()

        # --- ザグリのエンドミルの加工時間の算出 ---
        class ForCounterboreEndmill(PerfectCircleEndMill):
            def __init__(self, diameter, num_holes, depth, cutting_depth, tool_diameter, surface_speed, feed, cutting_allowance, cutting_length: float):
                self._diameter = diameter
                self._num_holes = num_holes
                self._depth = depth
                self._cutting_depth = cutting_depth
                self._tool_diameter = tool_diameter
                self._surface_speed = surface_speed
                self._feed = feed
                self._cutting_allowance = cutting_allowance
                self._cutting_length = cutting_length

                # --- 加工時間の算出 ---
                self.processing_time_min = self._calc_processing_time()
                self.processing_time_sec = self.processing_time_min * 60
                ## 四捨五入
                self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
                self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

                # --- その他の算出 ---
                self.pilot_hole = self._calc_pilot_hole()
                self.non_processing_time = self._calc_non_processing_time()
                self.long_setup_time = self._calc_long_setup_time()
                self.short_setup_time = self._calc_short_setup_time()

            def _calc_cutting_length(self):
                """
                切削長を算出するメソッド

                Returns
                    cutting_length: 切削長 [mm]
                """
                cutting_length = self._cutting_length
                return cutting_length

        endmill = ForCounterboreEndmill(
            diameter=self._counterbore_diameter,
            num_holes=self._num_holes,
            depth=self._counterbore_depth,
            cutting_depth=self._cutting_depth,
            tool_diameter=self._endmill_tool_diameter,
            surface_speed=self._endmill_surface_speed,
            feed=self._endmill_feed,
            cutting_allowance=self._cutting_allowance,
            cutting_length=self._calc_cutting_length()
        )

        endmill_processing_time_min = endmill._calc_processing_time()

        # --- 合算 ---
        processing_time_min = (drill_processing_time_min + endmill_processing_time_min)

        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 30 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 454 + self._num_holes * 40
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 334 + self._num_holes * 40
        return short_setup_time
    
class Milling:
    """
    フライスを条件から加工時間を算出するクラス

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """
    ROUGH_TOOL_DIAMETER: float = 100
    ROUGH_TOOL_SURFACE_SPEED: float = 230
    ROUGH_TOOL_FEED: float = 1.8
    CUTTING_DEPTH: float = 2
    TOOL_LENGTH: float = 105
    FINISHING_TOOL_DIAMETER: float = 125
    FINISHING_TOOL_SURFACE_SPEED: float = 245
    FINISHING_TOOL_FEED: float = 1

    def __init__(
        self,
        depth: float,
        surface_roughness: int,
        cutting_allowance_width: float,
        cutting_allowance_length: float,
        is_double_sided: bool,
    ):
        """
        Args:
            depth: 深さ [mm]
            surface_roughness: 面粗度（1~3）
            cutting_allowance_width: 取り代（幅）
            cutting_allowance_length: 取り代（長さ）
            is_double_sided: 両面加工の有無（Trueで両面加工）
        """
        self._depth = depth
        self._surface_roughness = surface_roughness
        self._cutting_allowance_width = cutting_allowance_width
        self._cutting_allowance_length = cutting_allowance_length
        self._is_double_sided = is_double_sided

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_cutting_length(self, tool_diameter: float) -> float:
        """
        切削長を算出するメソッド

        Args:
            tool_diameter: 工具長 [mm]

        Returns
            cutting_length: 切削長 [mm]
        """
        cutting_length = (
            self._cutting_allowance_length + (tool_diameter * 0.7 * 2)
        ) * (self._cutting_allowance_width / (tool_diameter * 0.7))
        return cutting_length

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        # --- 両面加工するか否か ---
        if self._is_double_sided == True:
            factor = 2
        else:
            factor = 1

        # --- 粗加工 ---
        if self._surface_roughness == 1:
            rough_cutting_length = self._calc_cutting_length(
                tool_diameter=self.ROUGH_TOOL_DIAMETER
            )
            rough_revolutions_per_minute = calc_rpm(
                surface_speed=self.ROUGH_TOOL_SURFACE_SPEED,
                diameter=self.ROUGH_TOOL_DIAMETER,
            )
            num_cutting_depths = calc_num_cutting_depths(
                depth=self._depth, cutting_depth=self.CUTTING_DEPTH
            )
            rough_processing_time_min = (rough_cutting_length * num_cutting_depths) / (
                self.ROUGH_TOOL_FEED * rough_revolutions_per_minute
            )
            processing_time_min = rough_processing_time_min
            return processing_time_min * factor

        # --- 仕上げ加工 ---
        finishing_cutting_length = self._calc_cutting_length(
            tool_diameter=self.FINISHING_TOOL_DIAMETER
        )
        finishing_revolutions_per_minute = calc_rpm(
            surface_speed=self.FINISHING_TOOL_SURFACE_SPEED,
            diameter=self.FINISHING_TOOL_DIAMETER,
        )
        rough_cutting_length = self._calc_cutting_length(
            tool_diameter=self.ROUGH_TOOL_DIAMETER
        )
        rough_revolutions_per_minute = calc_rpm(
            surface_speed=self.ROUGH_TOOL_SURFACE_SPEED,
            diameter=self.ROUGH_TOOL_DIAMETER,
        )
        num_cutting_depths = calc_num_cutting_depths(
            depth=self._depth, cutting_depth=self.CUTTING_DEPTH
        )
        rough_processing_time_min = (rough_cutting_length * num_cutting_depths) / (
            self.ROUGH_TOOL_FEED * rough_revolutions_per_minute
        )
        finishing_processing_time_min = finishing_cutting_length / (
            self.FINISHING_TOOL_FEED * finishing_revolutions_per_minute
        )
        processing_time_min = rough_processing_time_min + finishing_processing_time_min
        return processing_time_min * factor

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        if self._is_double_sided == True:
            non_processing_time = 20
        else:
            non_processing_time = 10
        return non_processing_time

    def _calc_long_setup_time(self) -> float:
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        if self._is_double_sided == True:
            long_setup_time = 560
        else:
            long_setup_time = 295
        return long_setup_time

    def _calc_short_setup_time(self) -> float:
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        if self._is_double_sided == True:
            short_setup_time = 470
        else:
            short_setup_time = 205
        return short_setup_time
    
class Chamfer:
    """
    ザグリを条件から加工時間を算出するクラス（真円、側面共通）

    Attributes:
        processing_time_min: 加工時間（分） [min]
        processing_time_sec: 加工時間（秒） [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]
    """

    def __init__(
        self,
        angle: float,
        chamfering_width: float,
        max_chamfering_width: float,
        tool_diameter: float,
        surface_speed: float,
        feed: float,
        diameter: float = None,
        num_holes: int = 0,
        cutting_length: float = None,
        min_corner_radius: float = None,
    ):
        """
        Args:
            angle: 角度 [°]
            chamfering_width: 加工幅 [mm]
            max_chamfering_width: 最大面取り幅 [mm]
            tool_diameter: 工具径 [mm]
            surface_speed: 周速 [m/min]
            feed: 送り [mm/rev]
            diameter: 加工径 [mm] ※真円の場合は指定する
            num_holes: 穴数 ※真円の場合は指定する（初期値: 0）
            cutting_length: 切削長 [mm] ※側面の場合は指定する
            min_corner_radius: 最小内R [mm] ※側面の場合は指定する
        """
        self._angle = angle
        self._chamfering_width = chamfering_width
        self._max_chamfering_width = max_chamfering_width
        self._tool_diameter = tool_diameter
        self._surface_speed = surface_speed
        self._feed = feed
        self._diameter = diameter
        self._num_holes = num_holes
        self._cutting_length = cutting_length
        self._min_corner_radius = min_corner_radius

        # --- 加工時間の算出 ---
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

        # --- その他の算出 ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_num_chamfers(self) -> int:
        """
        面取り回数を算出するメソッド

        Returns:
            num_chamfers: 面取り回数
        """
        if self._chamfering_width >= self._max_chamfering_width * 0.6:
            num_chamfers = 2
        else:
            num_chamfers = 1
        return num_chamfers

    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time_min: 加工時間（分） [min]
        """
        # --- 最小内R ---
        if self._min_corner_radius == None:
            self._min_corner_radius = self._diameter / 2

        # --- 切削長 ---
        if self._cutting_length == None:
            self._cutting_length = self._diameter * math.pi * self._num_holes

        #  --- 加工時間 ---
        revolutions_per_minute = calc_rpm(
            surface_speed=self._surface_speed, diameter=self._tool_diameter
        )
        feed_speed = calc_feed_speed(feed=self._feed, rpm=revolutions_per_minute)
        num_chamfers = self._calc_num_chamfers()
        processing_time_min = (self._cutting_length / feed_speed) * num_chamfers
        return processing_time_min

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 非加工時間 [min]
        """
        non_processing_time = 10 + self._num_holes * 3
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        if self._num_holes != 0:
            long_setup_time = 220 + self._num_holes * 40
        else:
            long_setup_time = 245
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        if self._num_holes != 0:
            short_setup_time = 100 + self._num_holes * 40
        else:
            short_setup_time = 125
        return short_setup_time



if __name__ == "__main__":
    # --- 対応可能機械 ---
    ccm = CheckCompatibleMachines(
        is_parallel_shapes=False,
        thickness=3.2,
        width=150,
        length=777,
        max_tool_length=230,
    )
    print("\n--- 対応可能機械 ---")
    print(f"M1-1号機: {ccm.can_process_M1_1}")
    print(f"M1-2号機: {ccm.can_process_M1_2}")
    print(f"M1-3号機: {ccm.can_process_M1_3}")
    print(f"M1-4号機: {ccm.can_process_M1_4}")
    print(f"M1-7号機: {ccm.can_process_M1_7}")

    # --- ドリル ---
    drill = Drill(diameter=12, surface_speed=100, depth=15.5, feed=0.25, num_holes=6)
    print("\n--- ドリル ---")
    print(f"加工時間（分）: {drill.processing_time_min}")
    print(f"加工時間（秒）: {drill.processing_time_sec}")
    print(f"非加工時間: {drill.non_processing_time}")
    print(f"段取時間(長): {drill.long_setup_time}")
    print(f"段取時間(短): {drill.short_setup_time}")

    # --- タップ ---
    tap = Tap(
        diameter=6,
        surface_speed=15,
        depth=10,
        feed=1,
        num_holes=3,
        pilot_diameter=5.54,
        pilot_surface_speed=100,
        pilot_feed=0.15,
    )
    print("\n--- タップ ---")
    print(f"加工時間（分）: {tap.processing_time_min}")
    print(f"加工時間（秒）: {tap.processing_time_sec}")
    print(f"非加工時間: {tap.non_processing_time}")
    print(f"段取時間(長): {tap.long_setup_time}")
    print(f"段取時間(短): {tap.short_setup_time}")

    # --- エンドミル ---
    endmill = PerfectCircleEndMill(
        diameter=100,
        num_holes=2,
        depth=25,
        cutting_depth=20,
        tool_diameter=16,
        surface_speed=100,
        feed=0.25,
        cutting_allowance=2
    )
    print("\n--- 真円 ---")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"下穴径: {endmill.pilot_hole}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")

    endmill = SideEndMill(
        depth=25,
        cutting_depth=20,
        tool_diameter=16,
        surface_speed=100,
        feed=0.25,
        cutting_length=600,
    )
    print("\n--- 側面 ---")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"切削長: {endmill.cutting_length}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")

    endmill = LongHoleEndMill(
        width=20,
        length=100,
        num_holes=3,
        depth=25,
        cutting_depth=15,
        tool_diameter=10,
        surface_speed=80,
        feed=0.2,
    )
    print("\n--- 長穴 ---")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"切削長: {endmill.cutting_length}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")

    # --- ボーリング ---
    boring = Boring(
        welded_hole=0,
        boring_diameter=30,
        boring_surface_speed=180,
        depth=10,
        boring_feed=0.08,
        num_holes=3,
        cutting_depth=20,
        endmill_tool_diameter=16,
        endmill_surface_speed=100,
        endmill_feed=0.25,
        cutting_allowance=2,
        drill_diameter=29,
        drill_surface_speed=180,
        drill_feed=0.08
    )
    print("\n--- ボーリング ---")
    print(f"加工時間（分）: {boring.processing_time_min}")
    print(f"加工時間（秒）: {boring.processing_time_sec}")
    print(f"下穴径: {boring.pilot_diameter}")
    print(f"非加工時間: {boring.non_processing_time}")
    print(f"段取時間(長): {boring.long_setup_time}")
    print(f"段取時間(短): {boring.short_setup_time}")

    # --- リーマ ---
    reamer = Reamer(
        reamer_diameter=20,
        reamer_surface_speed=8,
        reamer_feed=0.3,
        depth=10,
        num_holes=3,
        pilot_diameter=19.8,
        cutting_depth=20,
        endmill_tool_diameter=16,
        endmill_surface_speed=100,
        endmill_feed=0.25,
        cutting_allowance=2,
        drill_diameter=19.7,
        drill_surface_speed=32,
        drill_feed=0.35
    )

    print("\n--- リーマ ---")
    print(f"加工時間（分）: {reamer.processing_time_min}")
    print(f"加工時間（秒）: {reamer.processing_time_sec}")
    print(f"非加工時間: {reamer.non_processing_time}")
    print(f"段取時間(長): {reamer.long_setup_time}")
    print(f"段取時間(短): {reamer.short_setup_time}")

    # --- ザグリ ---
    counterbore = Counterbore(
        counterbore_diameter=30,
        counterbore_depth=10,
        drill_diameter=20,
        depth=15,
        num_holes=3,
        cutting_depth=1.5,
        provisional_endmill_tool_diameter=16,
        endmill_tool_diameter=4,
        endmill_surface_speed=50,
        endmill_feed=0.15,
        drill_surface_speed=100,
        drill_feed=0.35
    )

    print("\n--- ザグリ ---")
    print(f"加工時間（分）: {counterbore.processing_time_min}")
    print(f"加工時間（秒）: {counterbore.processing_time_sec}")
    print(f"非加工時間: {counterbore.non_processing_time}")
    print(f"段取時間(長): {counterbore.long_setup_time}")
    print(f"段取時間(短): {counterbore.short_setup_time}")

    # --- フライス ---
    milling = Milling(
        depth=2,
        surface_roughness=3,
        cutting_allowance_width=50,
        cutting_allowance_length=100,
        is_double_sided=True,
    )

    print("\n--- フライス ---")
    print(f"加工時間（分）: {milling.processing_time_min}")
    print(f"加工時間（秒）: {milling.processing_time_sec}")
    print(f"非加工時間: {milling.non_processing_time}")
    print(f"段取時間(長): {milling.long_setup_time}")
    print(f"段取時間(短): {milling.short_setup_time}")

    # --- 真円面取り ---
    chamfer = Chamfer(
        angle=45,
        chamfering_width=2,
        max_chamfering_width=7,
        tool_diameter=16,
        surface_speed=150,
        feed=0.15,
        diameter=30,
        num_holes=3,
    )

    print("\n--- 真円面取り ---")
    print(f"加工時間（分）: {chamfer.processing_time_min}")
    print(f"加工時間（秒）: {chamfer.processing_time_sec}")
    print(f"非加工時間: {chamfer.non_processing_time}")
    print(f"段取時間(長): {chamfer.long_setup_time}")
    print(f"段取時間(短): {chamfer.short_setup_time}")

    # --- 面取り（側面） ---
    chamfer = Chamfer(
        angle=45,
        chamfering_width=2,
        max_chamfering_width=7,
        tool_diameter=16,
        surface_speed=150,
        feed=0.15,
        cutting_length=100,
        min_corner_radius=999,
    )

    print("\n--- 面取り（側面） ---")
    print(f"加工時間（分）: {chamfer.processing_time_min}")
    print(f"加工時間（秒）: {chamfer.processing_time_sec}")
    print(f"非加工時間: {chamfer.non_processing_time}")
    print(f"段取時間(長): {chamfer.long_setup_time}")
    print(f"段取時間(短): {chamfer.short_setup_time}")