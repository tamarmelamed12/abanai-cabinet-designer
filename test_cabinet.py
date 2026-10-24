import pytest

from cabinet import (DOOR, DRAWER, ROD, SHELF, build_panels, cut_list, default_col_widths,
                     even_shelves, price)

W, H, D, T, B = 1000, 2000, 600, 18, 8


def build(n_cols=1, items=()):
    return build_panels(W, H, D, T, B, default_col_widths(W, T, n_cols), list(items))


def test_empty_cabinet_is_carcass_plus_back():
    panels = build()
    assert sorted(p.name for p in panels) == sorted(["דופן", "דופן", "תחתית", "תקרה", "גב"])
    top = next(p for p in panels if p.name == "תקרה")
    assert (top.w, top.d, top.h) == (W - 2 * T, D - B, T)


def test_dividers_per_column_count():
    assert sum(p.name == "מחיצה" for p in build(3)) == 2


def test_shelf_width_matches_column():
    widths = default_col_widths(W, T, 2)
    shelf = [p for p in build(2, [{"col": 2, "type": SHELF, "z": 500, "height": None}]) if p.kind == "shelf"]
    assert len(shelf) == 1 and shelf[0].w == widths[1] and shelf[0].x == T + widths[0] + T


def test_drawer_has_front_and_box():
    names = [p.name for p in build(items=[{"col": 1, "type": DRAWER, "z": 100, "height": 200}])]
    assert names.count("חזית מגירה") == 1 and names.count("צד מגירה") == 2
    assert "גב מגירה" in names and "תחתית מגירה" in names


def test_rod_not_in_cut_list():
    panels = build(items=[{"col": 1, "type": ROD, "z": 1700, "height": None}])
    assert any(p.kind == "rod" for p in panels)
    assert "מוט תלייה" not in set(cut_list(panels)["שם"])


def test_cut_list_groups_identical():
    df = cut_list(build())
    assert df.loc[df["שם"] == "דופן", "כמות"].item() == 2


def test_price():
    panels = build(items=[{"col": 1, "type": DOOR, "z": T, "height": H - 2 * T}])
    r = price(panels, price_m2_board=100, price_m2_back=10, drawer_rail=0, hinge_per_door=30)
    assert r["back_m2"] == pytest.approx(W * H / 1e6)
    assert r["hardware"] == 30
    assert r["total"] == pytest.approx(r["board_m2"] * 100 + r["back_m2"] * 10 + 30)


@pytest.mark.parametrize("item", [
    {"col": 1, "type": SHELF, "z": H, "height": None},
    {"col": 5, "type": SHELF, "z": 500, "height": None},
    {"col": 1, "type": DRAWER, "z": 100, "height": None},
])
def test_invalid_item_raises(item):
    with pytest.raises(ValueError):
        build(items=[item])


def test_bad_col_widths_raise():
    with pytest.raises(ValueError):
        build_panels(W, H, D, T, B, [400, 400], [])


def test_even_shelves_equal_gaps():
    zs = even_shelves(H, T, 3)
    edges = [T] + [e for z in zs for e in (z, z + T)] + [H - T]
    gaps = [edges[i + 1] - edges[i] for i in range(0, len(edges), 2)]
    assert gaps == pytest.approx([gaps[0]] * 4)

# Binder fitting: dimensions are clear internal spaces, not external dimensions.
from binder_fit import Binder, binder_spaces


def fit_spaces(items=(), **kwargs):
    args = dict(height=1000, depth=400, t=18, back_t=8,
                col_widths=[500], items=items, binder=Binder())
    args.update(kwargs)
    return binder_spaces(**args)


def test_binder_empty_cabinet_capacity():
    s = fit_spaces()[0]
    assert (s['height'], s['depth'], s['capacity']) == (964, 392, 6)


def test_binder_shelf_thickness_and_shortfall():
    spaces = fit_spaces([dict(col=1, type=SHELF, z=340, height=0)])
    assert len(spaces) == 2
    assert spaces[0]['missing_height'] == 8
    assert spaces[1]['bottom'] == 358


def test_binder_exact_fit_and_one_mm_short():
    base = dict(height=366, depth=308, col_widths=[90])
    assert fit_spaces(**base)[0]['fits']
    for change, field in [({'height': 365}, 'missing_height'),
                          ({'depth': 307}, 'missing_depth'),
                          ({'col_widths': [89]}, 'missing_width')]:
        result = fit_spaces(**dict(base, **change))[0]
        assert not result['fits']
        assert result[field] == 1


def test_binder_overlapping_obstacles_merge():
    items = [dict(col=1, type=DRAWER, z=18, height=400),
             dict(col=1, type=SHELF, z=300, height=0)]
    assert fit_spaces(items)[0]['bottom'] == 418


def test_binder_columns_independent_and_doors_ignored():
    items = [dict(col=1, type=DRAWER, z=18, height=600),
             dict(col=2, type=DOOR, z=18, height=964)]
    spaces = fit_spaces(items, col_widths=[100, 500])
    assert [s['bottom'] for s in spaces] == [618, 18]
    assert spaces[1]['x'] == 136


def test_binder_rod_is_conservative_obstacle():
    spaces = fit_spaces([dict(col=1, type=ROD, z=500, height=0)])
    assert [(s['bottom'], s['top']) for s in spaces] == [(18, 500), (525, 982)]


def test_binder_fully_blocked_column():
    assert fit_spaces([dict(col=1, type=DRAWER, z=18, height=964)]) == []


def test_binder_invalid_dimensions():
    for key in ('height', 'depth', 'spine'):
        for value in (0, -1, float('nan'), float('inf'), True):
            with pytest.raises(ValueError):
                Binder(**{key: value})
    assert Binder(clearance=0).clearance == 0


def test_binder_leaves_items_unchanged():
    items = [dict(col=1, type=SHELF, z=400, height=0)]
    before = [dict(item) for item in items]
    fit_spaces(items)
    assert items == before


def test_binder_app_loads_and_reacts_to_dimensions():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(Path(__file__).with_name('app.py'))).run(timeout=30)
    assert not app.exception
    assert any(tab.label == 'בדיקת קלסרים' for tab in app.tabs)
    assert app.number_input(key='binder_height').value == 320
    app.number_input(key='binder_height').set_value(600).run(timeout=30)
    assert not app.exception
    assert app.number_input(key='binder_height').value == 600
