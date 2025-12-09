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
        """
        self._diameter = diameter
        self._num_holes = num_holes
        self._depth = depth
        self._cutting_depth = cutting_depth
        self._tool_diameter = tool_diameter
        self._surface_speed = surface_speed
        self._feed = feed

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

    def _calc_cutting_length(self) -> float:
        """
        切削長を算出するメソッド

        Returns:
            cutting_length: 切削長 [mm]
        """
        cutting_length = self._diameter * math.pi * self._num_holes
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
        self._cutting_length = cutting_length

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
            (self._cutting_length * num_cutting_depths) / feed_speed
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
        self.processing_time_min = self._calc_processing_time()
        self.processing_time_sec = self.processing_time_min * 60
        ## 四捨五入
        self.processing_time_min = rounding_two_decimal(value=self.processing_time_min)
        self.processing_time_sec = rounding_two_decimal(value=self.processing_time_sec)

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
        processing_time_min = ((cutting_length * num_cutting_depths) / feed_speed) * 1.3
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



if __name__ == "__main__":
    # --- 対応可能機械 ---
    ccm = CheckCompatibleMachines(
        is_parallel_shapes=False,
        thickness=3.2,
        width=150,
        length=777,
        max_tool_length=230,
    )
    print("--- 対応可能機械 ---")
    print(f"M1-1号機: {ccm.can_process_M1_1}")
    print(f"M1-2号機: {ccm.can_process_M1_2}")
    print(f"M1-3号機: {ccm.can_process_M1_3}")
    print(f"M1-4号機: {ccm.can_process_M1_4}")
    print(f"M1-7号機: {ccm.can_process_M1_7}")

    # --- ドリル ---
    drill = Drill(diameter=12, surface_speed=100, depth=15.5, feed=0.25, num_holes=6)
    print("ドリル")
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
    print("タップ")
    print(f"加工時間（分）: {tap.processing_time_min}")
    print(f"加工時間（秒）: {tap.processing_time_sec}")
    print(f"非加工時間: {tap.non_processing_time}")
    print(f"段取時間(長): {tap.long_setup_time}")
    print(f"段取時間(短): {tap.short_setup_time}")

    # --- エンドミル ---
    endmill = PerfectCircleEndMill(
        diameter=50,
        num_holes=2,
        depth=10,
        cutting_depth=20,
        tool_diameter=16,
        surface_speed=100,
        feed=0.25,
    )
    print("真円")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")

    endmill = SideEndMill(
        depth=20,
        cutting_depth=20,
        tool_diameter=16,
        surface_speed=100,
        feed=0.25,
        cutting_length=200,
    )
    print("側面")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")

    endmill = LongHoleEndMill(
        width=20,
        length=100,
        num_holes=4,
        depth=5,
        cutting_depth=15,
        tool_diameter=10,
        surface_speed=80,
        feed=0.2,
    )
    print("長穴")
    print(f"加工時間（分）: {endmill.processing_time_min}")
    print(f"加工時間（秒）: {endmill.processing_time_sec}")
    print(f"非加工時間: {endmill.non_processing_time}")
    print(f"段取時間(長): {endmill.long_setup_time}")
    print(f"段取時間(短): {endmill.short_setup_time}")