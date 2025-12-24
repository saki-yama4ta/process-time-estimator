from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .calculations import (
    CheckCompatibleMachines,
    Drill,
    Tap,
    PerfectCircleEndMill,
    SideEndMill,
    LongHoleEndMill,
    Boring,
    Reamer,
    Counterbore,
    Milling,
    Chamfer,
    calc_removal_time,
    calc_rpm,
    calc_weight,
)


def calculator_view(request):
    # 現時点ではUIを表示するだけです。
    # 今後、計算ロジックなどをここに追加していきます。
    return render(request, "calculator/index.html")


# def _seconds_from_minutes_rounded(minutes: float) -> float:
#     """
#     分[min]を秒[s]に換算し、小数第2位で四捨五入して返す。
#     """
#     return float(
#         (Decimal(str(minutes)) * Decimal(60)).quantize(
#             Decimal("0.01"), rounding=ROUND_HALF_UP
#         )
#     )


def _parse_dimension_param(request, param_name: str) -> float:
    raw_value = request.GET.get(param_name)
    if raw_value in (None, ""):
        raise ValueError(f"{param_name}が指定されていません。")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{param_name}には数値を指定してください。") from exc
    if value < 0:
        raise ValueError(f"{param_name}は0以上を指定してください。")
    return value


def _parse_bool_param(request, param_name: str) -> bool:
    raw_value = request.GET.get(param_name)
    if raw_value is None:
        raise ValueError(f"{param_name}が指定されていません。")
    lowered = raw_value.lower()
    if lowered in ("1", "true", "on", "yes"):
        return True
    if lowered in ("0", "false", "off", "no"):
        return False
    raise ValueError(f"{param_name}にはtrue/falseを指定してください。")


def _fetch_drill_tool_conditions(
    diameter: Decimal, required_depth: float | None = None
):
    params = [diameter]
    depth_clause = ""
    if required_depth is not None:
        depth_clause = "AND depth >= %s"
        params.append(required_depth)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT surface_speed, feed, depth, tool_name, tool_length
              FROM drill_tools
             WHERE diameter = %s
            {depth_clause}
             ORDER BY id ASC
             LIMIT 1
            """,
            params,
        )
        row = cursor.fetchone()

    if not row:
        raise LookupError("drill tool not found")
    return row


def _fetch_tap_tool_conditions(
    diameter: Decimal,
    required_depth: float,
    pitch: float | None = None,
    *,
    exact_depth: bool = False,
):
    depth_decimal = Decimal(str(required_depth))

    clauses = [
        "diameter ~ '^[0-9.]+$'",
        "CAST(diameter AS NUMERIC) = %s",
    ]
    params = [diameter]

    # 深さは常に「required_depth以上」で検索する
    depth_clause = "CAST(depth AS NUMERIC) >= %s"
    clauses.append("depth ~ '^[0-9.]+$'")
    clauses.append(depth_clause)
    params.append(depth_decimal)

    if pitch is not None:
        clauses.append("pitch ~ '^[0-9.]+$'")
        clauses.append("CAST(pitch AS NUMERIC) = %s")
        params.append(Decimal(str(pitch)))

    where_sql = " AND ".join(clauses)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT surface_speed,
                   feed,
                   depth,
                   pilot_hole_diameter,
                   pitch,
                   tool_name,
                   tool_length
              FROM tap_tools
             WHERE {where_sql}
             ORDER BY depth ASC, id ASC
             LIMIT 1
            """,
            params,
        )
        row = cursor.fetchone()

    if not row:
        raise LookupError("tap tool not found")

    return row


def _fetch_endmill_tool_conditions(
    machining_type: str,
    removal_width: float,
    required_edge_radius: float,
    min_inner_radius: float,
    pref_list_override: list[int] | None = None,
):
    """
    エンドミル/長穴の工具選定ロジック。
    条件:
      - 刃長 > 取り代(幅)
      - φ/2 が最小内R以下
      - 刃先Rが0なら edge_radius <= 1 を許容、0以外なら完全一致
      - 優先径を持つものを優先（真円:16,33,26 / 側面:16,33,10,26 / 長穴:16,33,10,26）
      - 工具長は (刃長+120) と tool_length_min の大きい方
      - 切り込み量は取り代(幅) < 工具径×0.2 なら cut_depth_side、そうでなければ cut_depth_slot
    """
    # 優先値は全種共通で 16, 33, 10, 26（上書き指定があればそれを使う）
    pref_list = pref_list_override if pref_list_override is not None else [16, 33, 10, 26]

    edge_clause = (
        "(edge_radius IS NULL OR edge_radius <= 1)"
        if required_edge_radius == 0
        else "edge_radius = %s"
    )

    clauses = [
        "CAST(diameter AS TEXT) ~ '^[0-9.]+$'",
        "blade_length >= %s",  # 刃長が取り代以上であれば可
        "(CAST(diameter AS NUMERIC) / 2) <= %s",
        edge_clause,
    ]
    params: list[Decimal | float] = [removal_width, min_inner_radius]
    if required_edge_radius != 0:
        params.append(required_edge_radius)

    where_sql = " AND ".join(clauses)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id,
                   CAST(diameter AS NUMERIC) AS diameter_num,
                   surface_speed,
                   feed,
                   cut_depth_slot,
            cut_depth_side,
            blade_length,
            tool_length_min,
            edge_radius,
            tool_name,
            joint_m
              FROM end_mill_tools
             WHERE {where_sql}
             ORDER BY id ASC
            """,
            params,
        )
        rows = cursor.fetchall()

    if not rows:
        raise LookupError("endmill tool not found")

    def preference_rank(dia: float) -> int:
        try:
            d_int = int(round(dia))
        except Exception:
            return 10_000
        if d_int in pref_list:
            return pref_list.index(d_int)
        return 9_999

    candidates = []
    for row in rows:
        (
            row_id,
            diameter_num,
            surface_speed,
            feed,
            cut_depth_slot,
            cut_depth_side,
            blade_length,
            tool_length_min,
            edge_radius,
            tool_name,
            joint_m,
        ) = row

        try:
            dia_val = float(diameter_num)
        except (TypeError, ValueError):
            continue

        try:
            blade_length_val = float(blade_length)
            tool_length_min_val = float(tool_length_min)
        except (TypeError, ValueError):
            continue

        # 取り代(幅)と工具径から切り込み量を決定
        cut_depth_choice = (
            cut_depth_side if removal_width < dia_val * 0.2 else cut_depth_slot
        )

        tool_length_calc = max(blade_length_val + 120, tool_length_min_val)

        rank = preference_rank(dia_val)
        safe_tool_name = (tool_name or joint_m or "").strip()

        candidates.append(
            (
                rank,
                dia_val,
                row_id,
                surface_speed,
                feed,
                cut_depth_choice,
                blade_length_val,
                tool_length_calc,
                edge_radius,
                safe_tool_name,
            )
        )

    if not candidates:
        raise LookupError("endmill tool not found")

    candidates.sort()
    (
        _,
        dia_val,
        _,
        surface_speed,
        feed,
        cut_depth_choice,
        blade_length_val,
        tool_length_calc,
        edge_radius,
        tool_name,
    ) = candidates[0]

    return {
        "diameter": dia_val,
        "surface_speed": float(surface_speed) if surface_speed is not None else None,
        "feed": float(feed) if feed is not None else None,
        "cut_depth": float(cut_depth_choice) if cut_depth_choice is not None else None,
        "blade_length": blade_length_val,
        "tool_length": tool_length_calc,
        "edge_radius": float(edge_radius) if edge_radius is not None else None,
        "tool_name": tool_name,
    }


def _calc_drill_cycle_time_minutes(
    surface_speed: float,
    diameter: float,
    depth: float,
    feed: float,
    num_holes: int,
) -> float:
    """
    Drillクラスと同じ計算式で1サイクルの加工時間[min]を算出する。
    """
    revolutions_per_minute = calc_rpm(surface_speed=surface_speed, diameter=diameter)
    return (((depth / (feed * revolutions_per_minute)) * 60) * 2) * num_holes / 60






def _parse_tap_diameter(raw_value: str) -> Decimal:
    if raw_value in (None, ""):
        raise ValueError("tap_mが指定されていません。")
    normalized = raw_value.strip().upper()
    if normalized.startswith("M"):
        normalized = normalized[1:]
    normalized = normalized.replace("×", "x")
    normalized = normalized.split("X")[0]
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("tap_mの形式が不正です。")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("tap_mには有効な呼び径を入力してください。") from exc


@require_GET
def calculate_weight_view(request):
    """calc_weightの薄板重量を返すシンプルなAPI"""

    try:
        thickness = _parse_dimension_param(request, "plate_thickness")
        width = _parse_dimension_param(request, "width")
        length = _parse_dimension_param(request, "length")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    weight = calc_weight(thickness=thickness, width=width, length=length)
    return JsonResponse({"weight": weight})


@require_GET
def calculate_removal_time_view(request):
    """calc_weightとcalc_removal_timeを組み合わせて脱着時間を求めるAPI"""

    try:
        thickness = _parse_dimension_param(request, "plate_thickness")
        width = _parse_dimension_param(request, "width")
        length = _parse_dimension_param(request, "length")
        weight = _parse_dimension_param(request, "weight")
        is_parallel_shapes = _parse_bool_param(request, "vise_parallel")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    removal_time = calc_removal_time(weight=weight, is_parallel_shapes=is_parallel_shapes)
    compatible_machines = CheckCompatibleMachines(
        is_parallel_shapes=is_parallel_shapes,
        thickness=thickness,
        width=width,
        length=length,
        max_tool_length=0.0,
    )
    machines = {
        "M1-1": compatible_machines.can_process_M1_1,
        "M1-2": compatible_machines.can_process_M1_2,
        "M1-3": compatible_machines.can_process_M1_3,
        "M1-4": compatible_machines.can_process_M1_4,
        "M1-7": compatible_machines.can_process_M1_7,
    }
    return JsonResponse({"removal_time": removal_time, "machines": machines})


@require_GET
def drill_tool_conditions_view(request):
    """
    drill_toolsの径から周速/送りを取得するAPI

    Later on the caller will plug the returned値 into加工時間の式.
    """

    tool_type = request.GET.get("tool_type")
    diameter_param = request.GET.get("diameter")

    if tool_type in (None, ""):
        return JsonResponse({"error": "tool_typeを指定してください。"}, status=400)
    if diameter_param in (None, ""):
        return JsonResponse({"error": "diameterを指定してください。"}, status=400)

    try:
        diameter = Decimal(diameter_param)
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "diameterには数値を指定してください。"}, status=400)

    try:
        surface_speed, feed, max_depth, tool_name, tool_length = _fetch_drill_tool_conditions(
            diameter=diameter
        )
    except LookupError:
        return JsonResponse(
            {"error": "条件に一致する工具が見つかりませんでした。"}, status=404
        )

    try:
        surface_speed_value = float(surface_speed)
        feed_value = float(feed)
        depth_value = float(max_depth)
        tool_length_value = float(tool_length) if tool_length is not None else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "工具データを数値に変換できませんでした。"}, status=500)

    return JsonResponse(
        {
            "surface_speed": surface_speed_value,
            "feed": feed_value,
            "depth": depth_value,
            "tool_name": tool_name,
            "tool_length": tool_length_value,
        }
    )


@require_GET
def calculate_drill_process_view(request):
    """drill_toolsの条件と入力値からドリル加工時間を算出するAPI"""

    tool_type = request.GET.get("tool_type")
    if tool_type in (None, ""):
        return JsonResponse({"error": "tool_typeを指定してください。"}, status=400)

    diameter_param = request.GET.get("diameter")
    if diameter_param in (None, ""):
        return JsonResponse({"error": "diameterを指定してください。"}, status=400)
    try:
        diameter_decimal = Decimal(diameter_param)
        diameter = float(diameter_decimal)
    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "diameterには数値を指定してください。"}, status=400)
    if diameter <= 0:
        return JsonResponse({"error": "diameterは0より大きい値を指定してください。"}, status=400)

    penetration = request.GET.get("penetration") in ("1", "true", "on", "yes")
    try:
        depth = _parse_dimension_param(request, "depth")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if penetration:
        try:
            plate_thickness = _parse_dimension_param(request, "plate_thickness")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        depth = plate_thickness

    if depth <= 0:
        return JsonResponse({"error": "深さが未入力です。"}, status=400)

    num_holes_param = request.GET.get("num_holes")
    if num_holes_param in (None, ""):
        return JsonResponse({"error": "num_holesを指定してください。"}, status=400)
    try:
        num_holes = int(num_holes_param)
    except ValueError:
        return JsonResponse({"error": "num_holesには整数を指定してください。"}, status=400)
    if num_holes <= 0:
        return JsonResponse({"error": "num_holesは1以上を指定してください。"}, status=400)

    try:
        surface_speed, feed, max_depth, tool_name, tool_length = _fetch_drill_tool_conditions(
            diameter=diameter_decimal,
        )
    except LookupError:
        return JsonResponse(
            {"error": "条件に一致する工具が見つかりませんでした。"}, status=404
        )

    try:
        surface_speed_value = float(surface_speed)
        feed_value = float(feed)
        max_depth_value = float(max_depth)
        tool_length_value = float(tool_length) if tool_length is not None else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "工具データを数値に変換できませんでした。"}, status=500)

    if max_depth_value < depth:
        return JsonResponse(
            {"error": "加工不可：工具の対応深さを超えています。"}, status=400
        )

    drill = Drill(
        diameter=diameter,
        surface_speed=surface_speed_value,
        depth=depth,
        feed=feed_value,
        num_holes=num_holes,
    )

    processing_minutes = drill.processing_time_min
    processing_seconds = drill.processing_time_sec

    return JsonResponse(
        {
            "tool_type": tool_type,
            "tool_name": tool_name,
            "tool_length": tool_length_value,
            "diameter": diameter,
            "depth": depth,
            "surface_speed": surface_speed_value,
            "feed": feed_value,
            "processing_time_minutes": processing_minutes,
            "processing_time_seconds": processing_seconds,
            "non_processing_time": drill.non_processing_time,
            "setup_long_time": drill.long_setup_time,
            "setup_short_time": drill.short_setup_time,
        }
    )


@require_GET
def calculate_tap_process_view(request):
    """tap_toolsを利用してタップ加工時間を算出するAPI"""

    tool_type = request.GET.get("tool_type")
    if tool_type in (None, ""):
        return JsonResponse({"error": "tool_typeを指定してください。"}, status=400)

    raw_m = request.GET.get("tap_m")
    normalized_input = (raw_m or "").strip().upper()
    try:
        diameter_decimal = _parse_tap_diameter(raw_m or "")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # 表示用（M10 等）
    diameter_display = raw_m.strip() if raw_m else f"M{diameter_decimal}"

    penetration = request.GET.get("penetration") in ("1", "true", "on", "yes")
    try:
        depth = _parse_dimension_param(request, "depth")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # 貫通のときは板厚を深さとして使う
    if penetration:
        try:
            plate_thickness = _parse_dimension_param(request, "plate_thickness")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        depth = plate_thickness

    if depth <= 0:
        return JsonResponse({"error": "深さが未入力です。"}, status=400)

    # ピッチ（細目指定された場合のみ）。並目チェックONなら未指定扱い
    pitch_param = request.GET.get("pitch")
    pitch_value = None
    if pitch_param not in (None, ""):
        try:
            pitch_value = float(pitch_param)
            if pitch_value <= 0:
                return JsonResponse({"error": "ピッチは0より大きい値を指定してください。"}, status=400)
        except ValueError:
            return JsonResponse({"error": "ピッチには数値を指定してください。"}, status=400)

    num_holes_param = request.GET.get("num_holes")
    if num_holes_param in (None, ""):
        return JsonResponse({"error": "num_holesを指定してください。"}, status=400)
    try:
        num_holes = int(num_holes_param)
    except ValueError:
        return JsonResponse({"error": "num_holesには整数を指定してください。"}, status=400)
    if num_holes <= 0:
        return JsonResponse({"error": "num_holesは1以上を指定してください。"}, status=400)

    # --- タップ条件の検索 ---
    try:
        if pitch_value is not None:
            # ピッチが入力されている場合：
            #   タップ径 + ピッチ + 深さ(以上) で検索
            surface_speed, db_feed, max_depth, pilot_hole, db_pitch, tool_name, tool_length = (
                _fetch_tap_tool_conditions(
                    diameter=diameter_decimal,
                    required_depth=depth,
                    pitch=pitch_value,
                    exact_depth=False,
                )
            )
        else:
            # ピッチ未入力の場合：
            #   タップ径 + 「深さ = depth（板厚）」で一致する行を探し、
            #   その行の pitch を採用する
            surface_speed, db_feed, max_depth, pilot_hole, db_pitch, tool_name, tool_length = (
                _fetch_tap_tool_conditions(
                    diameter=diameter_decimal,
                    required_depth=depth,
                    pitch=None,
                    exact_depth=True,
                )
            )
    except LookupError:
        return JsonResponse(
            {"error": "条件に一致する工具が見つかりませんでした。"}, status=404
        )

    if pilot_hole in (None, ""):
        return JsonResponse({"error": "加工不可：下穴条件が登録されていません。"}, status=400)

    try:
        surface_speed_value = float(surface_speed)
        max_depth_value = float(max_depth)
        pilot_hole_value = float(pilot_hole)
        tool_length_value = float(tool_length) if tool_length is not None else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "加工不可：工具データが不正です。"}, status=400)

    db_pitch_value = None
    if db_pitch is not None:
        try:
            db_pitch_value = float(db_pitch)
        except (TypeError, ValueError):
            return JsonResponse({"error": "加工不可：ピッチ情報が不正です。"}, status=400)

    db_feed_value = None
    if db_feed is not None:
        try:
            db_feed_value = float(db_feed)
        except (TypeError, ValueError):
            return JsonResponse({"error": "加工不可：送り情報が不正です。"}, status=400)

    if max_depth_value < depth:
        return JsonResponse(
            {"error": "加工不可：工具の対応深さを超えています。"}, status=400
        )

    effective_pitch = pitch_value if pitch_value is not None else db_pitch_value
    if effective_pitch is None:
        return JsonResponse(
            {"error": "加工不可：ピッチ情報が取得できませんでした。"}, status=400
        )

    # 送りの優先順位: DB送りがあればそれを使用、なければピッチと同じ値
    feed_value = db_feed_value if db_feed_value is not None else float(effective_pitch)

    try:
        (
            pilot_surface_speed,
            pilot_feed,
            _,
            _,
            _,
        ) = _fetch_drill_tool_conditions(
            diameter=Decimal(str(pilot_hole_value)),
            required_depth=depth,
        )
    except LookupError:
        return JsonResponse(
            {"error": "加工不可：下穴条件に一致する工具が見つかりませんでした。"}, status=404
        )

    try:
        pilot_surface_speed_value = float(pilot_surface_speed)
        pilot_feed_value = float(pilot_feed)
    except (TypeError, ValueError):
        return JsonResponse({"error": "加工不可：下穴工具データが不正です。"}, status=400)

    tap = Tap(
        diameter=float(diameter_decimal),
        surface_speed=surface_speed_value,
        depth=depth,
        feed=feed_value,
        num_holes=num_holes,
        pilot_diameter=pilot_hole_value,
        pilot_surface_speed=pilot_surface_speed_value,
        pilot_feed=pilot_feed_value,
    )

    # tap_cut_minutes = _calc_drill_cycle_time_minutes(
    #     surface_speed=surface_speed_value,
    #     diameter=float(diameter_decimal),
    #     depth=depth,
    #     feed=feed_value,
    #     num_holes=num_holes,
    # )
    # pilot_cut_minutes = _calc_drill_cycle_time_minutes(
    #     surface_speed=pilot_surface_speed_value,
    #     diameter=pilot_hole_value,
    #     depth=depth,
    #     feed=pilot_feed_value,
    #     num_holes=num_holes,
    # )
    
    #total_minutes = tap_cut_minutes + pilot_cut_minutes
    processing_minutes = tap.processing_time_min
    processing_seconds = tap.processing_time_sec

    return JsonResponse(
        {
            "tool_type": tool_type,
            "tool_name": tool_name,
            "tool_length": tool_length_value,
            "diameter": diameter_display,
            "depth": depth,
            # クライアント側に返すピッチ：
            #   入力があればその値、なければ DB から拾った値
            "pitch": float(effective_pitch),
            "pilot_hole_diameter": pilot_hole_value,
            "surface_speed": surface_speed_value,
            "feed": feed_value,
            "processing_time_minutes": processing_minutes,
            "processing_time_seconds": processing_seconds,
            "non_processing_time": tap.non_processing_time,
            "setup_long_time": tap.long_setup_time,
            "setup_short_time": tap.short_setup_time,
        }
    )


# ========== エンドミル系 ==========


def _parse_depth_with_penetration(request, depth_param: str, penetration_param: str) -> float:
    depth = _parse_dimension_param(request, depth_param)
    penetration = request.GET.get(penetration_param) in ("1", "true", "on", "yes")
    if penetration:
        plate_thickness = _parse_dimension_param(request, "plate_thickness")
        depth = plate_thickness
    if depth <= 0:
        raise ValueError("深さが未入力です。")
    return depth


def _build_endmill_response(tool_name, tool_length, processing_time_min, processing_time_sec, non_proc, long_setup, short_setup, diameter, depth, process_label):
    safe_tool_name = tool_name or process_label or "エンドミル"
    return {
        "process_label": process_label,
        "tool_name": safe_tool_name,
        "tool_length": tool_length,
        "diameter": diameter,
        "depth": depth,
        "processing_time_minutes": processing_time_min,
        "processing_time_seconds": processing_time_sec,
        "non_processing_time": non_proc,
        "setup_long_time": long_setup,
        "setup_short_time": short_setup,
        "pilot_hole_diameter": None,
        "cutting_length": None,
    }


@require_GET
def calculate_endmill_circle_view(request):
    """エンドミル(真円)の加工時間を算出するAPI"""
    try:
        depth = _parse_depth_with_penetration(request, "depth", "penetration")
        removal = _parse_dimension_param(request, "removal")
        edge_radius = float(request.GET.get("edge_radius", 0) or 0)
        machining_diameter = _parse_dimension_param(request, "machining_diameter")
        num_holes = int(_parse_dimension_param(request, "num_holes"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    min_inner_radius = machining_diameter / 2

    try:
        tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            removal_width=removal,
            required_edge_radius=edge_radius,
            min_inner_radius=min_inner_radius,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if tool["surface_speed"] is None or tool["feed"] is None or tool["cut_depth"] is None:
        return JsonResponse({"error": "加工不可：工具データが不足しています。"}, status=400)

    endmill = PerfectCircleEndMill(
        diameter=machining_diameter,
        num_holes=num_holes,
        depth=depth,
        cutting_depth=tool["cut_depth"],
        tool_diameter=tool["diameter"],
        surface_speed=tool["surface_speed"],
        feed=tool["feed"],
        cutting_allowance=removal,
    )

    resp = _build_endmill_response(
        tool_name=tool["tool_name"],
        tool_length=tool["tool_length"],
        processing_time_min=endmill.processing_time_min,
        processing_time_sec=endmill.processing_time_sec,
        non_proc=endmill.non_processing_time,
        long_setup=endmill.long_setup_time,
        short_setup=endmill.short_setup_time,
        diameter=machining_diameter,
        depth=depth,
        process_label="エンドミル(真円)",
    )
    resp["pilot_hole_diameter"] = getattr(endmill, "pilot_hole", None)
    resp["cutting_length"] = getattr(endmill, "_calc_cutting_length", lambda: None)()

    return JsonResponse(resp)


@require_GET
def calculate_endmill_side_view(request):
    """エンドミル(側面)の加工時間を算出するAPI"""
    try:
        depth = _parse_depth_with_penetration(request, "depth", "penetration")
        removal = _parse_dimension_param(request, "removal")
        edge_radius = float(request.GET.get("edge_radius", 0) or 0)
        cutting_length = _parse_dimension_param(request, "cutting_length")
        min_inner_radius = _parse_dimension_param(request, "min_inner_radius")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        tool = _fetch_endmill_tool_conditions(
            machining_type="side",
            removal_width=removal,
            required_edge_radius=edge_radius,
            min_inner_radius=min_inner_radius,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if tool["surface_speed"] is None or tool["feed"] is None or tool["cut_depth"] is None:
        return JsonResponse({"error": "加工不可：工具データが不足しています。"}, status=400)

    endmill = SideEndMill(
        depth=depth,
        cutting_depth=tool["cut_depth"],
        tool_diameter=tool["diameter"],
        surface_speed=tool["surface_speed"],
        feed=tool["feed"],
        cutting_length=cutting_length,
    )

    resp = _build_endmill_response(
        tool_name=tool["tool_name"],
        tool_length=tool["tool_length"],
        processing_time_min=endmill.processing_time_min,
        processing_time_sec=endmill.processing_time_sec,
        non_proc=endmill.non_processing_time,
        long_setup=endmill.long_setup_time,
        short_setup=endmill.short_setup_time,
        diameter=tool["diameter"],
        depth=depth,
        process_label="エンドミル(側面)",
    )
    resp["cutting_length"] = cutting_length

    return JsonResponse(resp)


@require_GET
def calculate_endmill_slot_view(request):
    """長孔の加工時間を算出するAPI"""
    try:
        width = _parse_dimension_param(request, "width")
        length = _parse_dimension_param(request, "length")
        depth = _parse_depth_with_penetration(request, "depth", "penetration")
        edge_radius = float(request.GET.get("edge_radius", 0) or 0)
        num_holes = int(_parse_dimension_param(request, "num_holes"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    min_inner_radius = width / 2

    try:
        tool = _fetch_endmill_tool_conditions(
            machining_type="longhole",
            removal_width=width,
            required_edge_radius=edge_radius,
            min_inner_radius=min_inner_radius,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if tool["surface_speed"] is None or tool["feed"] is None or tool["cut_depth"] is None:
        return JsonResponse({"error": "加工不可：工具データが不足しています。"}, status=400)

    endmill = LongHoleEndMill(
        width=width,
        length=length,
        num_holes=num_holes,
        depth=depth,
        cutting_depth=tool["cut_depth"],
        tool_diameter=tool["diameter"],
        surface_speed=tool["surface_speed"],
        feed=tool["feed"],
    )

    resp = _build_endmill_response(
        tool_name=tool["tool_name"],
        tool_length=tool["tool_length"],
        processing_time_min=endmill.processing_time_min,
        processing_time_sec=endmill.processing_time_sec,
        non_proc=endmill.non_processing_time,
        long_setup=endmill.long_setup_time,
        short_setup=endmill.short_setup_time,
        diameter=tool["diameter"],
        depth=depth,
        process_label="長孔",
    )
    resp["cutting_length"] = getattr(endmill, "cutting_length", None)

    return JsonResponse(resp)

@require_GET
def calculate_boring_process_view(request):
    """
    ボーリング + 下穴ドリル + 底さらえエンドミル をまとめて計算する API。

    クエリパラメータ:
        boring_diameter: ボーリング加工径 [mm]
        depth: 加工深さ [mm]
        num_holes: 穴数
        welded_hole: 溶断孔径 [mm]（0 または空なら「溶断孔なし」とみなす）
        cutting_allowance: 取り代 [mm]（省略時は 2.0）
    """
    # --- 入力パラメータ ---
    try:
        boring_diameter = _parse_dimension_param(request, "boring_diameter")
        depth = _parse_dimension_param(request, "depth")
        num_holes_raw = request.GET.get("num_holes")
        if num_holes_raw in (None, ""):
            raise ValueError("num_holesが指定されていません。")
        num_holes = int(num_holes_raw)
        if num_holes <= 0:
            raise ValueError("num_holesは1以上を指定してください。")

        # 溶断孔 (0 または未指定なら「なし」扱い)
        welded_hole_param = request.GET.get("welded_hole", "0")
        welded_hole = float(welded_hole_param or 0)

        # 取り代（エンドミル用）。Excel 互換で 2mm をデフォルトとする
        cutting_allowance_param = request.GET.get("cutting_allowance")
        cutting_allowance = float(cutting_allowance_param) if cutting_allowance_param not in (None, "") else 2.0

    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if depth <= 0:
        return JsonResponse({"error": "depthは0より大きい値を指定してください。"}, status=400)

    # --- ボーリング工具の選定 ---
    try:
        boring_tool = _select_best_boring_tool(
            boring_diameter=boring_diameter,
            required_depth=depth,
        )
    except LookupError as exc:
        return JsonResponse({"error": f"加工不可：{exc}"}, status=404)

    if boring_tool["surface_speed"] is None or boring_tool["feed"] is None:
        return JsonResponse({"error": "加工不可：ボーリング工具データが不足しています。"}, status=400)

    # --- エンドミル（底さらえ）の選定 ---
    # 下穴径 = ボーリング径 - 0.2
    pilot_diameter = boring_diameter - 0.2
    if pilot_diameter <= 0:
        return JsonResponse({"error": "加工不可：下穴径が0以下です。"}, status=400)

    try:
        endmill_tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            removal_width=cutting_allowance,
            required_edge_radius=0.0,
            min_inner_radius=pilot_diameter / 2.0,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if (
        endmill_tool["surface_speed"] is None
        or endmill_tool["feed"] is None
        or endmill_tool["cut_depth"] is None
    ):
        return JsonResponse({"error": "加工不可：エンドミル工具データが不足しています。"}, status=400)

    # --- ドリル（溶断孔が無い場合だけ） ---
    drill_tool = None
    if welded_hole == 0:
        try:
            drill_tool = _fetch_drill_for_boring(
                pilot_diameter=pilot_diameter,
                required_depth=depth,
            )
        except LookupError:
            return JsonResponse(
                {"error": "加工不可：下穴条件に一致するドリルが見つかりませんでした。"}, status=404
            )

    # --- Boring クラスでトータル加工時間を算出 ---
    boring_obj = Boring(
        welded_hole=welded_hole,
        boring_diameter=boring_diameter,
        boring_surface_speed=boring_tool["surface_speed"],
        depth=depth,
        boring_feed=boring_tool["feed"],
        num_holes=num_holes,
        cutting_depth=endmill_tool["cut_depth"],
        endmill_tool_diameter=endmill_tool["diameter"],
        endmill_surface_speed=endmill_tool["surface_speed"],
        endmill_feed=endmill_tool["feed"],
        cutting_allowance=cutting_allowance,
        drill_diameter=drill_tool["diameter"] if drill_tool else None,
        drill_surface_speed=drill_tool["surface_speed"] if drill_tool else None,
        drill_feed=drill_tool["feed"] if drill_tool else None,
    )

    # --- レスポンス構築 ---
    response = {
        "tool_type": "boring",
        "process_label": "ボーリング",

        # 入力条件
        "boring_diameter": boring_diameter,
        "depth": depth,
        "num_holes": num_holes,
        "welded_hole": welded_hole,
        "cutting_allowance": cutting_allowance,

        # ボーリング工具情報
        "boring_tool_name": boring_tool["tool_name"],
        "boring_surface_speed": boring_tool["surface_speed"],
        "boring_feed": boring_tool["feed"],
        "boring_base_depth": boring_tool["base_depth"],          # 最大深さ
        "boring_tool_length": boring_tool["tool_length_total"],  # 最大深さ + R 合計（最適解）

        # エンドミル（底さらえ）
        "pilot_diameter": boring_obj.pilot_diameter,
        "endmill_tool_name": endmill_tool["tool_name"],
        "endmill_tool_diameter": endmill_tool["diameter"],
        "endmill_surface_speed": endmill_tool["surface_speed"],
        "endmill_feed": endmill_tool["feed"],
        "endmill_cut_depth": endmill_tool["cut_depth"],
        "endmill_tool_length": endmill_tool["tool_length"],

        # ドリル（溶断孔なしのときだけ有効）
        "drill_diameter": drill_tool["diameter"] if drill_tool else None,
        "drill_tool_name": drill_tool["tool_name"] if drill_tool else None,
        "drill_surface_speed": drill_tool["surface_speed"] if drill_tool else None,
        "drill_feed": drill_tool["feed"] if drill_tool else None,
        "drill_tool_length": drill_tool["tool_length"] if drill_tool else None,

        # 時間情報
        "processing_time_minutes": boring_obj.processing_time_min,
        "processing_time_seconds": boring_obj.processing_time_sec,
        "non_processing_time": boring_obj.non_processing_time,
        "setup_long_time": boring_obj.long_setup_time,
        "setup_short_time": boring_obj.short_setup_time,
    }

    return JsonResponse(response)
def _fetch_boring_candidate_rows(boring_diameter: float):
    """
    boring_tools テーブルから、指定径が範囲に入る行をすべて取得する。
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id,
                   min_diameter,
                   max_diameter,
                   depth,
                   surface_speed,
                   feed,
                   tool_length,
                   tool_name
              FROM boring_tools
             WHERE (min_diameter IS NULL OR CAST(min_diameter AS NUMERIC) <= %s)
               AND (max_diameter IS NULL OR CAST(max_diameter AS NUMERIC) >= %s)
             ORDER BY depth ASC, id ASC
            """,
            [boring_diameter, boring_diameter],
        )
        rows = cursor.fetchall()
    return rows


def _fetch_boring_joint_lengths(base_depth: float) -> list[float]:
    """
    boring_joint_tools から、min_diameter or max_diameter が base_depth と一致する
    ジョイントの工具長リストを取得。
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tool_length
              FROM boring_joint_tools
             WHERE min_diameter = %s
                OR max_diameter = %s
            """,
            [base_depth, base_depth],
        )
        rows = cursor.fetchall()

    r_list: list[float] = []
    for (tool_length,) in rows:
        try:
            r_val = float(tool_length)
        except (TypeError, ValueError):
            continue
        r_list.append(r_val)
    return r_list


def _select_best_boring_tool(
    boring_diameter: float,
    required_depth: float,
) -> dict:
    """
    Excel の BoringReamerBestMatch ロジックを DB 版で実装。

    - boring_tools から min_diameter <= φ <= max_diameter の行を候補とする
    - 各候補について baseD=depth が required_depth 以上なら、
      ジョイント (1〜3本) の組み合わせも含めて
      「baseD + sum(R) >= required_depth かつ (total - required_depth) が最小」
      になる total を求める
    - 全候補の中で diff が最小のものを「最適解」として返す
    """
    rows = _fetch_boring_candidate_rows(boring_diameter)
    if not rows:
        raise LookupError("boring tool not found (no diameter range matched)")

    global_min_diff = float("inf")
    best_result: dict | None = None

    for (
        row_id,
        min_d,
        max_d,
        depth,
        surface_speed,
        feed,
        base_tool_length,
        tool_name,
    ) in rows:
        try:
            base_depth = float(depth)
        except (TypeError, ValueError):
            continue

        # 最大深さそのものが深さを満たしていない場合は、この行は候補外（Excel と同じ）
        try:
            base_tool_length_val = float(base_tool_length)
        except (TypeError, ValueError):
            base_tool_length_val = None

        base_length_for_total = base_tool_length_val if base_tool_length_val is not None else base_depth

        # まず base_depth 単体での候補
        found_combo = False
        min_diff_for_row = float("inf")
        best_total_for_row = None

        if base_depth >= required_depth:
            diff = abs(base_depth - required_depth)
            best_total_for_row = base_length_for_total
            min_diff_for_row = diff
            found_combo = True

        # R 候補を取得
        r_list = _fetch_boring_joint_lengths(base_depth)

        n = len(r_list)
        # 1本
        for x in range(n):
            r_sum = r_list[x]
            coverage_total = base_depth + r_sum
            if coverage_total >= required_depth:
                diff = abs(coverage_total - required_depth)
                if diff < min_diff_for_row:
                    min_diff_for_row = diff
                    best_total_for_row = base_length_for_total + r_sum
                    found_combo = True

        # 2本
        for x in range(n):
            for y in range(x + 1, n):
                r_sum = r_list[x] + r_list[y]
                coverage_total = base_depth + r_sum
                if coverage_total >= required_depth:
                    diff = abs(coverage_total - required_depth)
                    if diff < min_diff_for_row:
                        min_diff_for_row = diff
                        best_total_for_row = base_length_for_total + r_sum
                        found_combo = True

        # 3本
        for x in range(n):
            for y in range(x + 1, n):
                for z in range(y + 1, n):
                    r_sum = r_list[x] + r_list[y] + r_list[z]
                    coverage_total = base_depth + r_sum
                    if coverage_total >= required_depth:
                        diff = abs(coverage_total - required_depth)
                        if diff < min_diff_for_row:
                            min_diff_for_row = diff
                            best_total_for_row = base_length_for_total + r_sum
                            found_combo = True

        if not found_combo or best_total_for_row is None:
            continue

        if min_diff_for_row < global_min_diff:
            global_min_diff = min_diff_for_row
            best_result = {
                "id": row_id,
                "min_diameter": float(min_d) if min_d is not None else None,
                "max_diameter": float(max_d) if max_d is not None else None,
                "base_depth": base_depth,
                "surface_speed": float(surface_speed) if surface_speed is not None else None,
                "feed": float(feed) if feed is not None else None,
                "base_tool_length": base_tool_length_val,
                # 最適な「工具長（最大深さ + R合計）」として扱う
                "tool_length_total": best_total_for_row,
                "tool_name": tool_name,
            }

    if not best_result:
        raise LookupError("boring tool not found (no depth combination matched)")

    return best_result


# ========== リーマ ==========
@require_GET
def calculate_reamer_process_view(request):
    """
    リーマの入力とDB条件から加工時間を算出するAPI
    """
    try:
        raw_dia = request.GET.get("reamer_diameter") or request.GET.get("diameter")
        if raw_dia in (None, ""):
            raise ValueError("reamer_diameterが指定されていません。")
        diameter = float(raw_dia)

        depth_param = "reamer_depth" if request.GET.get("reamer_depth") is not None else "depth"
        penetration_param = (
            "reamer_penetration" if request.GET.get("reamer_penetration") is not None else "penetration"
        )
        depth = _parse_depth_with_penetration(request, depth_param, penetration_param)

        raw_num_holes = request.GET.get("reamer_hole_count") or request.GET.get("num_holes")
        if raw_num_holes in (None, ""):
            raise ValueError("num_holesが指定されていません。")
        num_holes = int(raw_num_holes)
        if num_holes <= 0:
            raise ValueError("num_holesは1以上を入力してください。")

    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # リーマ工具取得
    try:
        reamer_surface_speed, reamer_feed, max_depth, pilot_hole_diameter, reamer_tool_length, reamer_tool_name = _fetch_reamer_tool_conditions(
            diameter=diameter, required_depth=depth
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するリーマ工具がありません。"}, status=404)

    try:
        reamer_surface_speed_val = float(reamer_surface_speed)
        reamer_feed_val = float(reamer_feed)
        max_depth_val = float(max_depth)
        pilot_hole_val = float(pilot_hole_diameter)
        reamer_tool_length_val = float(reamer_tool_length) if reamer_tool_length is not None else None
        reamer_tool_name_val = reamer_tool_name
    except (TypeError, ValueError):
        return JsonResponse({"error": "工具データを数値に変換できませんでした。"}, status=500)

    if max_depth_val < depth:
        return JsonResponse({"error": "加工不可：最大深さを超えています。"}, status=400)

    # 下穴用ドリル（パイロット径以下で最大）
    try:
        drill_tool = _fetch_drill_for_boring(pilot_diameter=pilot_hole_val, required_depth=depth)
    except LookupError:
        return JsonResponse({"error": "加工不可：下穴条件に一致するドリルが見つかりませんでした。"}, status=404)

    try:
        pilot_diameter_used = float(drill_tool["diameter"])
    except (TypeError, ValueError):
        return JsonResponse({"error": "下穴ドリルの径を数値に変換できませんでした。"}, status=500)

    # 底さらえ用エンドミル（加工径＝下穴径）。取り代は0mmで計算する
    cutting_allowance = 0.0
    try:
        endmill_tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            removal_width=cutting_allowance,
            required_edge_radius=0.0,
            min_inner_radius=pilot_diameter_used / 2.0,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if (
        endmill_tool["surface_speed"] is None
        or endmill_tool["feed"] is None
        or endmill_tool["cut_depth"] is None
    ):
        return JsonResponse({"error": "加工不可：エンドミルの条件が不足しています。"}, status=400)

    try:
        endmill_surface_speed = float(endmill_tool["surface_speed"])
        endmill_feed = float(endmill_tool["feed"])
        endmill_cut_depth = float(endmill_tool["cut_depth"])
        endmill_tool_diameter = float(endmill_tool["diameter"])
    except (TypeError, ValueError):
        return JsonResponse({"error": "工具データを数値に変換できませんでした。"}, status=500)

    try:
        reamer_obj = Reamer(
            reamer_diameter=diameter,
            reamer_surface_speed=reamer_surface_speed_val,
        reamer_feed=reamer_feed_val,
        depth=depth,
        num_holes=num_holes,
        pilot_diameter=pilot_diameter_used,
        cutting_depth=endmill_cut_depth,
        endmill_tool_diameter=endmill_tool_diameter,
        endmill_surface_speed=endmill_surface_speed,
        endmill_feed=endmill_feed,
        cutting_allowance=cutting_allowance,
            drill_diameter=drill_tool["diameter"],
            drill_surface_speed=drill_tool["surface_speed"],
            drill_feed=drill_tool["feed"],
        )
    except Exception as exc:
        return JsonResponse({"error": f"リーマ計算に失敗しました: {exc}"}, status=500)

    # 工具長はリーマ・エンドミル・ドリルの中で最大を返す
    length_candidates = []
    for val in (
        reamer_tool_length_val,
        endmill_tool.get("tool_length"),
        drill_tool.get("tool_length"),
    ):
        try:
            if val is not None:
                length_candidates.append(float(val))
        except (TypeError, ValueError):
            continue
    tool_length_max = max(length_candidates) if length_candidates else None

    processing_minutes = float(
        Decimal(str(reamer_obj.processing_time_min)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    processing_seconds = float(
        Decimal(str(reamer_obj.processing_time_sec)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    return JsonResponse(
        {
            "process_label": "リーマ",
            "tool_name": reamer_tool_name_val,
            "tool_length": tool_length_max,
            "diameter": diameter,
            "depth": depth,
            "pilot_hole_diameter": pilot_diameter_used,
            "processing_time_minutes": processing_minutes,
            "processing_time_seconds": processing_seconds,
            "non_processing_time": reamer_obj.non_processing_time,
            "setup_long_time": reamer_obj.long_setup_time,
            "setup_short_time": reamer_obj.short_setup_time,
        }
    )


# ========== ザグリ ==========

def _select_counterbore_endmill_diameter(hole_diameter: float) -> float:
    """
    優先径リストから穴径以下で最初に該当するものを返す。
    見つからなければ穴径そのものを返す。
    """
    priorities = [16, 33, 10, 26]
    for val in priorities:
        if val <= hole_diameter:
            return float(val)
    return float(hole_diameter)


@require_GET
def calculate_counterbore_process_view(request):
    """
    ザグリ：ドリル（穴径/穴深さ）＋ エンドミル（ザグリ径/ザグリ深さ）
    """
    try:
        counterbore_diameter = _parse_dimension_param(request, "counterbore_diameter")
        counterbore_depth = _parse_dimension_param(request, "counterbore_depth")
        hole_diameter = _parse_dimension_param(request, "counterbore_pore_diameter")
        # 穴深さは貫通対応
        hole_depth = _parse_depth_with_penetration(
            request,
            depth_param="counterbore_hole_depth",
            penetration_param="counterbore_penetration",
        )
        num_holes_raw = request.GET.get("counterbore_hole_count") or request.GET.get("num_holes")
        if num_holes_raw in (None, ""):
            raise ValueError("num_holesが指定されていません。")
        num_holes = int(num_holes_raw)
        if num_holes <= 0:
            raise ValueError("num_holesは1以上を入力してください。")
    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # ドリル（穴径/穴深さ）→ ドリル計算と同じ探索条件を使用
    try:
        drill_surface_speed, drill_feed, drill_depth, drill_tool_name, drill_tool_length = _fetch_drill_tool_conditions(
            diameter=Decimal(str(hole_diameter)), required_depth=hole_depth
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するドリルが見つかりませんでした。"}, status=404)

    try:
        drill_surface_speed_val = float(drill_surface_speed)
        drill_feed_val = float(drill_feed)
        drill_depth_val = float(drill_depth)
        drill_tool_length_val = float(drill_tool_length) if drill_tool_length is not None else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "ドリル工具データを数値に変換できませんでした。"}, status=500)

    if drill_depth_val < hole_depth:
        return JsonResponse({"error": "加工不可：ドリルの最大深さを超えています。"}, status=400)

    # エンドミル 1回目（仮工具径を取得）
    try:
        provisional_tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            removal_width=0.0,
            required_edge_radius=0.0,
            min_inner_radius=hole_diameter / 2.0,
            pref_list_override=[16, 33, 10, 26],  # 優先値
        )
        provisional_endmill_tool_diameter = float(provisional_tool["diameter"])
    except LookupError:
        provisional_endmill_tool_diameter = _select_counterbore_endmill_diameter(hole_diameter)
    except (TypeError, ValueError):
        provisional_endmill_tool_diameter = _select_counterbore_endmill_diameter(hole_diameter)

    # エンドミル 2回目（優先値なしで再探索）
    try:
        endmill_tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            # 本探索は溝側の切込量を使いたいので、取り代を大きめに渡してcut_depth_slotを採用
            removal_width=hole_diameter,
            required_edge_radius=0.0,
            min_inner_radius=hole_diameter / 2.0,
            pref_list_override=[],  # 優先値なし
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    if (
        endmill_tool["surface_speed"] is None
        or endmill_tool["feed"] is None
        or endmill_tool["cut_depth"] is None
    ):
        return JsonResponse({"error": "加工不可：エンドミルの条件が不足しています。"}, status=400)

    try:
        endmill_tool_diameter = float(endmill_tool["diameter"])
        endmill_surface_speed = float(endmill_tool["surface_speed"])
        endmill_feed = float(endmill_tool["feed"])
        endmill_cut_depth = float(endmill_tool["cut_depth"])
    except (TypeError, ValueError):
        return JsonResponse({"error": "エンドミル工具データを数値に変換できませんでした。"}, status=500)

    # Counterbore クラスで一括計算
    counter = Counterbore(
        counterbore_diameter=counterbore_diameter,
        counterbore_depth=counterbore_depth,
        drill_diameter=hole_diameter,
        depth=hole_depth,
        num_holes=num_holes,
        cutting_depth=endmill_cut_depth,
        provisional_endmill_tool_diameter=provisional_endmill_tool_diameter,
        endmill_tool_diameter=endmill_tool_diameter,
        endmill_surface_speed=endmill_surface_speed,
        endmill_feed=endmill_feed,
        drill_surface_speed=drill_surface_speed_val,
        drill_feed=drill_feed_val,
        cutting_allowance=0.0,
    )

    total_minutes = float(counter.processing_time_min)
    total_seconds = float(counter.processing_time_sec)
    non_processing = counter.non_processing_time
    setup_long = counter.long_setup_time
    setup_short = counter.short_setup_time

    # 工具長はドリル・エンドミルで最大を返す
    length_candidates = []
    for val in (
        drill_tool_length_val,
        endmill_tool.get("tool_length"),
    ):
        try:
            if val is not None:
                length_candidates.append(float(val))
        except (TypeError, ValueError):
            continue
    tool_length_max = max(length_candidates) if length_candidates else None

    return JsonResponse(
        {
            "process_label": "ザグリ",
            "tool_name": endmill_tool.get("tool_name"),
            "tool_length": tool_length_max,
            "diameter": endmill_tool_diameter,  # 加工径/工具径としてエンドミルの工具径を返す
            "depth": counterbore_depth,
            "pilot_hole_diameter": hole_diameter,
            "provisional_endmill_tool_diameter": provisional_endmill_tool_diameter,
            "endmill_tool_diameter": endmill_tool_diameter,
            "endmill_surface_speed": endmill_surface_speed,
            "endmill_feed": endmill_feed,
            "cutting_depth": endmill_cut_depth,
            "processing_time_minutes": total_minutes,
            "processing_time_seconds": total_seconds,
            "non_processing_time": non_processing,
            "setup_long_time": setup_long,
            "setup_short_time": setup_short,
        }
    )


@require_GET
def calculate_milling_process_view(request):
    """
    フライス(フェイスミル)の計算API（工具条件は固定）
    """
    try:
        depth = _parse_dimension_param(request, "milling_depth")
        surface_roughness = _parse_dimension_param(request, "milling_surface_roughness")
        removal_width = _parse_dimension_param(request, "milling_removal_width")
        removal_length = _parse_dimension_param(request, "milling_removal_length")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    cutting_surface_option = (
        request.GET.get("milling_cutting_surface_option")
        or request.GET.get("cutting_surface_option")
        or "one_side"
    )
    both_sides = cutting_surface_option == "both_sides"

    if depth <= 0 or removal_width <= 0 or removal_length <= 0:
        return JsonResponse(
            {"error": "加工条件が不足しています。正の値を入力してください。"},
            status=400,
        )

    if removal_width >= 750 or removal_length >= 1200 or surface_roughness >= 4:
        return JsonResponse(
            {"error": "加工不可：取り代または面粗度の条件外です。", "judge": "加工不可"},
            status=400,
        )

    milling_obj = Milling(
        depth=depth,
        surface_roughness=int(surface_roughness),
        cutting_allowance_width=removal_width,
        cutting_allowance_length=removal_length,
        is_double_sided=both_sides,
    )

    return JsonResponse(
        {
            "process_label": "フライス",
            "tool_name": "フライス",
            "tool_length": Milling.TOOL_LENGTH,
            "diameter": Milling.ROUGH_TOOL_DIAMETER if int(surface_roughness) == 1 else Milling.FINISHING_TOOL_DIAMETER,
            "processing_time_minutes": float(milling_obj.processing_time_min),
            "processing_time_seconds": float(milling_obj.processing_time_sec),
            "non_processing_time": milling_obj.non_processing_time,
            "setup_long_time": milling_obj.long_setup_time,
            "setup_short_time": milling_obj.short_setup_time,
            "judge": "加工可能",
        }
    )


def _fetch_chamfer_tool(angle: float, chamfer_width: float, min_inner_radius: float):
    """
    chamfer_tools から条件に合う工具を1件取得
    条件:
      - chamfer_angle == angle
      - chamfer_width < max_chamfer_width
      - (min_diameter / 2) <= min_inner_radius
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT chamfer_angle,
                   max_chamfer_width,
                   min_diameter,
                   surface_speed,
                   feed,
                   tool_length,
                   tool_name,
                   diameter
              FROM chamfer_tools
             WHERE chamfer_angle = %s
               AND %s < max_chamfer_width
               AND (min_diameter / 2.0) <= %s
             ORDER BY id ASC
             LIMIT 1
            """,
            [angle, chamfer_width, min_inner_radius],
        )
        row = cursor.fetchone()
    if not row:
        raise LookupError("chamfer tool not found")
    (
        chamfer_angle,
        max_chamfer_width,
        min_diameter,
        surface_speed,
        feed,
        tool_length,
        tool_name,
        diameter,
    ) = row
    return {
        "chamfer_angle": float(chamfer_angle),
        "max_chamfer_width": float(max_chamfer_width),
        "min_diameter": float(min_diameter),
        "surface_speed": float(surface_speed),
        "feed": float(feed),
        "tool_length": float(tool_length) if tool_length is not None else None,
        "tool_name": tool_name,
        "diameter": float(diameter) if diameter is not None else None,
    }


@require_GET
def calculate_chamfer_circle_view(request):
    """
    真円面取りの計算API
    """
    try:
        angle = _parse_dimension_param(request, "chamfer_circle_angle")
        processing_width = _parse_dimension_param(request, "chamfer_circle_processing_width")
        machining_diameter = _parse_dimension_param(request, "chamfer_circle_machining_diameter")
        num_holes = int(_parse_dimension_param(request, "chamfer_circle_hole_count"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if angle < 0 or angle > 180 or processing_width < 0 or machining_diameter < 0 or num_holes < 0:
        return JsonResponse({"error": "加工不可：角度/加工幅/加工径が条件外です。", "judge": "加工不可"}, status=400)
    min_inner_radius = machining_diameter / 2.0
    if min_inner_radius < 0:
        return JsonResponse({"error": "加工不可：最小内Rが条件外です。", "judge": "加工不可"}, status=400)

    try:
        tool = _fetch_chamfer_tool(angle=angle, chamfer_width=processing_width, min_inner_radius=min_inner_radius)
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致する面取り工具がありません。", "judge": "加工不可"}, status=404)

    chamfer_obj = Chamfer(
        angle=angle,
        chamfering_width=processing_width,
        max_chamfering_width=tool["max_chamfer_width"],
        tool_diameter=tool["diameter"] or machining_diameter,
        surface_speed=tool["surface_speed"],
        feed=tool["feed"],
        diameter=machining_diameter,
        num_holes=num_holes,
        cutting_length=None,
        min_corner_radius=min_inner_radius,
    )

    return JsonResponse(
        {
            "process_label": "面取り(真円)",
            "tool_name": tool["tool_name"],
            "tool_length": tool["tool_length"],
            "diameter": machining_diameter,
            "processing_time_minutes": float(chamfer_obj.processing_time_min),
            "processing_time_seconds": float(chamfer_obj.processing_time_sec),
            "non_processing_time": chamfer_obj.non_processing_time,
            "setup_long_time": chamfer_obj.long_setup_time,
            "setup_short_time": chamfer_obj.short_setup_time,
            "judge": "加工可能",
        }
    )


@require_GET
def calculate_chamfer_side_view(request):
    """
    面取り(側面)の計算API
    """
    try:
        angle = _parse_dimension_param(request, "chamfer_side_angle")
        processing_width = _parse_dimension_param(request, "chamfer_side_processing_width")
        cutting_length = _parse_dimension_param(request, "chamfer_side_cutting_length")
        min_inner_radius = _parse_dimension_param(request, "chamfer_side_minimum_inner_radius")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if angle < 0 or angle > 180 or processing_width < 0 or min_inner_radius < 0:
        return JsonResponse({"error": "加工不可：角度/加工幅/最小内Rが条件外です。", "judge": "加工不可"}, status=400)

    try:
        tool = _fetch_chamfer_tool(angle=angle, chamfer_width=processing_width, min_inner_radius=min_inner_radius)
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致する面取り工具がありません。", "judge": "加工不可"}, status=404)

    chamfer_obj = Chamfer(
        angle=angle,
        chamfering_width=processing_width,
        max_chamfering_width=tool["max_chamfer_width"],
        tool_diameter=tool["diameter"] or 0.0,
        surface_speed=tool["surface_speed"],
        feed=tool["feed"],
        diameter=None,
        num_holes=0,
        cutting_length=cutting_length,
        min_corner_radius=min_inner_radius,
    )

    return JsonResponse(
        {
            "process_label": "面取り(側面)",
            "tool_name": tool["tool_name"],
            "tool_length": tool["tool_length"],
            "diameter": "",
            "processing_time_minutes": float(chamfer_obj.processing_time_min),
            "processing_time_seconds": float(chamfer_obj.processing_time_sec),
            "non_processing_time": chamfer_obj.non_processing_time,
            "setup_long_time": chamfer_obj.long_setup_time,
            "setup_short_time": chamfer_obj.short_setup_time,
            "judge": "加工可能",
        }
    )

def _fetch_drill_for_boring(pilot_diameter: float, required_depth: float):
    """
    ドリル選定ロジック：
    - diameter <= pilot_diameter
    - depth >= required_depth
    - 条件を満たす中で diameter が最大になるものを 1件取得
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT diameter,
                   surface_speed,
                   feed,
                   depth,
                   tool_name,
                   tool_length
             FROM drill_tools
            WHERE diameter <= %s
              AND depth >= %s
             ORDER BY diameter DESC, depth ASC, tool_length DESC NULLS LAST, id ASC
             LIMIT 1
            """,
            [pilot_diameter, required_depth],
        )
        row = cursor.fetchone()

    if not row:
        raise LookupError("pilot drill tool not found")

    (
        diameter,
        surface_speed,
        feed,
        depth,
        tool_name,
        tool_length,
    ) = row

    return {
        "diameter": float(diameter),
        "surface_speed": float(surface_speed),
        "feed": float(feed),
        "depth": float(depth),
        "tool_name": tool_name,
        "tool_length": float(tool_length) if tool_length is not None else None,
    }


# reamer_tools から径一致・深さ条件を満たす工具を1件取得
def _fetch_reamer_tool_conditions(diameter: float, required_depth: float):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT surface_speed,
                   feed,
                   depth,
                   pilot_hole_diameter,
                   tool_length,
                   tool_name
              FROM reamer_tools
             WHERE diameter = %s
               AND depth >= %s
             ORDER BY depth ASC, id ASC
             LIMIT 1
            """,
            [diameter, required_depth],
        )
        row = cursor.fetchone()

    if not row:
        raise LookupError("reamer tool not found")

    return row

# UI のパラメータ名に合わせたボーリング計算ビュー（上書き用）
@require_GET
def calculate_boring_process_view(request):
    """
    ボーリング + 下穴ドリル + 底さらえエンドミル をまとめて計算する API
    """
    try:
        raw_dia = request.GET.get("boring_diameter") or request.GET.get("diameter")
        if raw_dia in (None, ""):
            raise ValueError("boring_diameterが指定されていません。")
        boring_diameter = float(raw_dia)

        depth_param = "boring_depth" if request.GET.get("boring_depth") is not None else "depth"
        penetration_param = (
            "boring_penetration" if request.GET.get("boring_penetration") is not None else "penetration"
        )
        depth = _parse_depth_with_penetration(request, depth_param, penetration_param)

        raw_num_holes = request.GET.get("boring_hole_count") or request.GET.get("num_holes")
        if raw_num_holes in (None, ""):
            raise ValueError("num_holesが指定されていません。")
        num_holes = int(raw_num_holes)
        if num_holes <= 0:
            raise ValueError("num_holesは1以上を入力してください。")

        welded_param = (
            request.GET.get("boring_fusing_hole")
            if request.GET.get("boring_fusing_hole") is not None
            else request.GET.get("welded_hole")
        )
        welded_hole = float(welded_param) if welded_param not in (None, "") else 0.0

        cutting_allowance_param = request.GET.get("cutting_allowance")
        cutting_allowance = float(cutting_allowance_param) if cutting_allowance_param not in (None, "") else 2.0
    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if boring_diameter <= 0:
        return JsonResponse({"error": "径は0より大きい値を入力してください。"}, status=400)
    if depth <= 0:
        return JsonResponse({"error": "depthは0より大きい値を指定してください。"}, status=400)

    # ボーリング工具を選定
    try:
        boring_tool = _select_best_boring_tool(
            boring_diameter=boring_diameter,
            required_depth=depth,
        )
    except LookupError as exc:
        return JsonResponse({"error": f"加工不可：{exc}"}, status=404)

    if boring_tool["surface_speed"] is None or boring_tool["feed"] is None:
        return JsonResponse({"error": "加工不可：ボーリング工具データが不足しています。"}, status=400)

    # 下穴径 = ボーリング径 - 0.2
    pilot_diameter = boring_diameter - 0.2
    if pilot_diameter <= 0:
        return JsonResponse({"error": "加工不可：下孔径が0以下です。"}, status=400)

    # 底さらえ用エンドミル
    try:
        endmill_tool = _fetch_endmill_tool_conditions(
            machining_type="circle",
            removal_width=cutting_allowance,
            required_edge_radius=0.0,
            min_inner_radius=pilot_diameter / 2.0,
        )
    except LookupError:
        return JsonResponse({"error": "加工不可：条件に一致するエンドミルがありません。"}, status=404)

    try:
        endmill_surface_speed = float(endmill_tool["surface_speed"])
        endmill_feed = float(endmill_tool["feed"])
        endmill_cut_depth = float(endmill_tool["cut_depth"])
        endmill_tool_diameter = float(endmill_tool["diameter"])
    except (TypeError, ValueError):
        return JsonResponse({"error": "工具データを数値に変換できませんでした。"}, status=500)

    if endmill_tool["surface_speed"] is None or endmill_tool["feed"] is None or endmill_tool["cut_depth"] is None:
        return JsonResponse({"error": "加工不可：エンドミルの条件が不足しています。"}, status=400)

    # 下穴ドリル（溶断孔が無い場合のみ）
    drill_tool = None
    drill_surface_speed = None
    drill_feed = None
    drill_diameter = None
    if welded_hole == 0:
        try:
            drill_tool = _fetch_drill_for_boring(pilot_diameter=pilot_diameter, required_depth=depth)
        except LookupError:
            return JsonResponse({"error": "加工不可：下穴条件に一致するドリルが見つかりませんでした。"}, status=404)

        drill_diameter = drill_tool["diameter"]
        drill_surface_speed = drill_tool["surface_speed"]
        drill_feed = drill_tool["feed"]

    try:
        boring = Boring(
            welded_hole=welded_hole,
            boring_diameter=boring_diameter,
            boring_surface_speed=boring_tool["surface_speed"],
            depth=depth,
            boring_feed=boring_tool["feed"],
            num_holes=num_holes,
            cutting_depth=endmill_cut_depth,
            endmill_tool_diameter=endmill_tool_diameter,
            endmill_surface_speed=endmill_surface_speed,
            endmill_feed=endmill_feed,
            cutting_allowance=cutting_allowance,
            drill_diameter=drill_diameter,
            drill_surface_speed=drill_surface_speed,
            drill_feed=drill_feed,
        )
    except Exception as exc:
        return JsonResponse({"error": f"ボーリング計算に失敗しました: {exc}"}, status=500)

    # 最大工具長を集約（ボーリング／エンドミル／ドリルで最大値を採用）
    length_candidates: list[float] = []
    for val in (
        boring_tool.get("tool_length_total"),
        boring_tool.get("base_tool_length"),
        boring_tool.get("tool_length"),  # 念のため生の工具長も候補に含める
        endmill_tool.get("tool_length"),
        drill_tool["tool_length"] if drill_tool else None,
    ):
        try:
            if val is not None:
                length_candidates.append(float(val))
        except (TypeError, ValueError):
            continue
    tool_length_max = max(length_candidates) if length_candidates else None

    return JsonResponse(
        {
            "process_label": "ボーリング",
            "tool_name": boring_tool.get("tool_name"),
            "tool_length": tool_length_max,
            "diameter": boring_diameter,
            "depth": depth,
            "pilot_hole_diameter": boring.pilot_diameter,
            "processing_time_minutes": boring.processing_time_min,
            "processing_time_seconds": boring.processing_time_sec,
            "non_processing_time": boring.non_processing_time,
            "setup_long_time": boring.long_setup_time,
            "setup_short_time": boring.short_setup_time,
        }
    )

