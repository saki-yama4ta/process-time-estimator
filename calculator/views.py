from decimal import Decimal, InvalidOperation

from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .calculations import (
    CheckCompatibleMachines,
    Drill,
    Tap,
    calc_removal_time,
    calc_rpm,
    calc_weight,
)


def calculator_view(request):
    # 現時点ではUIを表示するだけです。
    # 今後、計算ロジックなどをここに追加していきます。
    return render(request, "calculator/index.html")


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
    tool_type: str, diameter: Decimal, required_depth: float | None = None
):
    params = [tool_type, diameter]
    depth_clause = ""
    if required_depth is not None:
        depth_clause = "AND depth >= %s"
        params.append(required_depth)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT surface_speed, feed, depth, tool_name, tool_length
              FROM drill_tools
             WHERE tool_type = %s
               AND diameter = %s
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

    depth_clause = "CAST(depth AS NUMERIC) = %s" if exact_depth else "CAST(depth AS NUMERIC) >= %s"
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
            tool_type=tool_type, diameter=diameter
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
            tool_type=tool_type,
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
            {"error": "工具の対応深さを超えています。"}, status=400
        )

    drill = Drill(
        diameter=diameter,
        surface_speed=surface_speed_value,
        depth=depth,
        feed=feed_value,
        num_holes=num_holes,
    )

    processing_minutes = drill.processing_time
    processing_seconds = round(processing_minutes * 60, 2)

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
            return JsonResponse({"error": "DB????????????????????"}, status=500)

    if max_depth_value < depth:
        return JsonResponse(
            {"error": "加工不可：工具の対応深さを超えています。"}, status=400
        )

    effective_pitch = pitch_value if pitch_value is not None else db_pitch_value
    if effective_pitch is None:
        return JsonResponse(
            {"error": "加工不可：ピッチ情報が取得できませんでした。"}, status=400
        )

    feed_value = float(effective_pitch)

    try:
        (
            pilot_surface_speed,
            pilot_feed,
            _,
            _,
            _,
        ) = _fetch_drill_tool_conditions(
            tool_type="drill",
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

    tap_cut_minutes = _calc_drill_cycle_time_minutes(
        surface_speed=surface_speed_value,
        diameter=float(diameter_decimal),
        depth=depth,
        feed=feed_value,
        num_holes=num_holes,
    )
    pilot_cut_minutes = _calc_drill_cycle_time_minutes(
        surface_speed=pilot_surface_speed_value,
        diameter=pilot_hole_value,
        depth=depth,
        feed=pilot_feed_value,
        num_holes=num_holes,
    )
    total_minutes = tap_cut_minutes + pilot_cut_minutes
    processing_minutes = round(total_minutes, 2)
    processing_seconds = round(total_minutes * 60, 2)

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


