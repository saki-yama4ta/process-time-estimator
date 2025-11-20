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