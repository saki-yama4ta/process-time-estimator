"""
加工時間の算出式をまとめたファイル

Notes:
    有効数字は小数第2位まで
"""

import math


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


class Drill:
    """
    ドリル加工を条件から加工時間を算出するクラス

    Attributes:
        _diameter: ドリル径 [mm]
        _surface_speed: 周速 [m/min]
        _depth: 加工深さ [mm]
        _feed: 送り [mm/rev]
        _num_holes: 穴数
        processing_time: 加工時間 [min]
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
        self._diameter = diameter
        self._surface_speed = surface_speed
        self._depth = depth
        self._feed = feed
        self._num_holes = num_holes

        self._validate_value()
        self.processing_time = round(self._calc_processing_time(), 2)
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()


    def _validate_value(self):
        """値の妥当性を確認するメソッド"""
        if self._diameter <= 0:
            raise ValueError("ドリル径は0より大きい値を指定してください。")
        if self._surface_speed <= 0:
            raise ValueError("周速は0より大きい値を指定してください。")
        if self._feed <= 0:
            raise ValueError("送りは0より大きい値を指定してください。")
        if self._depth < 0:
            raise ValueError("深さは0より大きい値を指定してください。")
        if self._num_holes < 0:
            raise ValueError("穴数は1以上を指定してください。")


    def _calc_processing_time(self) -> float:
        """
        加工時間を算出するメソッド

        Returns:
            processing_time: 加工時間 [min]
        """
        revolutions_per_minute = calc_rpm(surface_speed=self._surface_speed, diameter=self._diameter)
        processing_time = (
            (((self._depth / (self._feed * revolutions_per_minute)) * 60) * 2)
            * self._num_holes
            / 60
        )
        return processing_time

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 加工時間 [min]
        """
        non_processing_time = 20 + self._num_holes * 5
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 244 + self._num_holes * 30
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 244 + self._num_holes * 20
        return short_setup_time


class Tap(Drill):
    """
    タップ加工を条件から加工時間を算出するクラス

    Attributes:
        _diameter: タップ径 [mm]
        _surface_speed: 周速 [m/min]
        _depth: 加工深さ [mm]
        _feed: 送り [mm/rev]
        _num_holes: 穴数
        _pilot_diameter: 下穴径 [mm]
        _pilot_surface_speed: 下穴の周速 [m/min]
        _pilot_feed: 下穴の送り [mm/rev]
        processing_time: 加工時間 [min]
        non_processing_time: 非加工時間 [sec]
        long_setup_time: 段取時間(長) [sec]
        short_setup_time: 段取時間(短) [sec]

    """
    def __init__(self, diameter, surface_speed, depth, feed, num_holes, pilot_diameter: float, pilot_surface_speed: float, pilot_feed: float):
        # --- タップの加工時間の算出 ---
        super().__init__(diameter, surface_speed, depth, feed, num_holes)
        tap_processing_time = self.processing_time

        # --- 下穴の加工時間の算出 ---
        self._pilot_diameter = pilot_diameter
        self._pilot_surface_speed = pilot_surface_speed
        self._pilot_feed = pilot_feed
        if self._pilot_diameter < 0:
            raise ValueError("下穴径は0より大きい値を指定してください。")
        if self._pilot_surface_speed < 0:
            raise ValueError("下穴の周速は0より大きい値を指定してください。")
        if self._pilot_feed <= 0:
            raise ValueError("下穴の送りは0より大きい値を指定してください。")
        drill = Drill(diameter=self._pilot_diameter, surface_speed=self._pilot_surface_speed, depth=self._depth, feed=self._pilot_feed, num_holes=self._num_holes)
        self.processing_time = round((tap_processing_time + drill.processing_time), 2)

        # --- まとめ ---
        self.non_processing_time = self._calc_non_processing_time()
        self.long_setup_time = self._calc_long_setup_time()
        self.short_setup_time = self._calc_short_setup_time()

    def _calc_non_processing_time(self) -> float:
        """
        非加工時間を算出するメソッド

        Returns:
            non_processing_time: 加工時間 [min]
        """
        non_processing_time = 40 + self._num_holes * 15
        return non_processing_time

    def _calc_long_setup_time(self):
        """
        段取時間(長)を算出するメソッド

        Returns:
            long_setup_time: 段取時間(長)
        """
        long_setup_time = 366 + self._num_holes * 30
        return long_setup_time

    def _calc_short_setup_time(self):
        """
        段取時間(短)を算出するメソッド

        Returns:
            short_setup_time: 段取時間(短)
        """
        short_setup_time = 150 + self._num_holes * 20
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
    print(f"加工時間: {drill.processing_time}")
    print(f"非加工時間: {drill.non_processing_time}")
    print(f"段取時間(長): {drill.long_setup_time}")
    print(f"段取時間(短): {drill.short_setup_time}")