"""Upright binder fit checks in millimetres; never changes cabinet geometry."""
from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True)
class Binder:
    height: float = 320
    depth: float = 290
    spine: float = 80
    clearance: float = 10

    def __post_init__(self):
        for name in ('height', 'depth', 'spine', 'clearance'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError('מידות הקלסר חייבות להיות מספרים סופיים')
            if value < 0 or (name != 'clearance' and value == 0):
                raise ValueError('מידות הקלסר חייבות להיות חיוביות; מרווח יכול להיות אפס')


def binder_spaces(height, depth, t, back_t, col_widths, items, binder):
    """Free vertical intervals; doors ignored, rods conservatively block full depth.

    Clearance is added once per compartment dimension. Overlapping obstacles
    are merged; shelves use their thickness and drawers their front height.
    """
    widths = list(col_widths)
    dimensions = [height, depth, t, back_t, *widths]
    if not widths or any(isinstance(v, bool) or not isinstance(v, (int, float))
                         or not isfinite(v) or v <= 0 for v in dimensions):
        raise ValueError('מידות הארון חייבות להיות חיוביות וסופיות')
    if height <= 2*t or depth <= back_t:
        raise ValueError('אין חלל פנימי בארון')
    blocked = [[] for _ in widths]
    for item in items:
        kind = item['type']
        if kind == 'דלת':
            continue
        if kind not in ('מדף', 'מגירה', 'מוט תלייה'):
            raise ValueError('סוג רכיב לא מוכר')
        col, z = item['col'], item['z']
        span = t if kind == 'מדף' else 25 if kind == 'מוט תלייה' else item['height']
        if type(col) is not int or not 1 <= col <= len(widths):
            raise ValueError('עמודה לא קיימת')
        if any(not isinstance(v, (int, float)) or not isfinite(v) for v in (z, span)) or span <= 0:
            raise ValueError('גובה רכיב לא תקין')
        low, high = max(t, z), min(height-t, z+span)
        if high > low:
            blocked[col-1].append((low, high))
    results = []
    x = t
    for col, (width, intervals) in enumerate(zip(widths, blocked), 1):
        cursor = t
        gaps = []
        for low, high in sorted(intervals):
            if low > cursor:
                gaps.append((cursor, low))
            cursor = max(cursor, high)
        if cursor < height-t:
            gaps.append((cursor, height-t))
        for index, (bottom, top) in enumerate(gaps, 1):
            available_h, available_d = top-bottom, depth-back_t
            missing_h = max(0, binder.height+binder.clearance-available_h)
            missing_d = max(0, binder.depth+binder.clearance-available_d)
            missing_w = max(0, binder.spine+binder.clearance-width)
            fits = not (missing_h or missing_d or missing_w)
            capacity = max(0, floor((width-binder.clearance)/binder.spine)) if fits else 0
            results.append(dict(col=col, space=index, x=x, bottom=bottom, top=top,
                                width=width, depth=available_d, height=available_h,
                                fits=fits, capacity=capacity, missing_height=missing_h,
                                missing_depth=missing_d, missing_width=missing_w))
        x += width+t
    return results


def render_binder_check(panels, height, depth, t, back_t, widths, items):
    """Optional Streamlit UI; dependencies are imported only when used."""
    import streamlit as st
    import plotly.graph_objects as go
    from view3d import figure, CX, CY, CZ, TI, TJ, TK

    st.subheader('📁 האם הקלסרים נכנסים?')
    st.caption('קלסרים עומדים, לפי המידות שתזיני. נבדק החלל הפנימי הפנוי, ולא המידות החיצוניות.')
    a, b, c, d = st.columns(4)
    bh = a.number_input('גובה קלסר (מ״מ)', 50, 600, 320, key='binder_height')
    bd = b.number_input('עומק קלסר (מ״מ)', 50, 600, 290, key='binder_depth')
    bs = c.number_input('עובי גב קלסר (מ״מ)', 10, 200, 80, key='binder_spine')
    gap = d.number_input('מרווח להכנסה (מ״מ)', 0, 50, 10, key='binder_clearance')
    binder = Binder(bh, bd, bs, gap)
    try:
        spaces = binder_spaces(height, depth, t, back_t, widths, items, binder)
    except ValueError as error:
        st.error(str(error))
        return
    st.metric('קיבולת משוערת לקלסרים', sum(s['capacity'] for s in spaces))
    if not spaces:
        st.info('לא נמצא חלל פנוי בין הרכיבים.')
        return
    table = []
    for s in spaces:
        missing = []
        for field, label in [('missing_height', 'גובה'), ('missing_depth', 'עומק'), ('missing_width', 'רוחב')]:
            if s[field] > 0:
                missing.append(f"חסרים {s[field]:.1f} מ״מ ב{label}")
        table.append({'עמודה': s['col'], 'חלל מלמטה': s['space'], 'גובה פנוי (מ״מ)': round(s['height'], 1),
                      'רוחב פנוי (מ״מ)': round(s['width'], 1), 'קלסרים': s['capacity'],
                      'תוצאה': 'מתאים' if s['fits'] else ' · '.join(missing)})
    st.dataframe(table, use_container_width=True, hide_index=True)
    fig = figure(panels, show_doors=False)
    for s in spaces:
        if not s['fits']:
            continue
        x, z = s['x']+gap/2, s['bottom']
        fig.add_trace(go.Mesh3d(x=[x+v*bs for v in CX], y=[v*bd for v in CY],
                               z=[z+v*bh for v in CZ], i=TI, j=TJ, k=TK,
                               color='#38a169', opacity=0.85, flatshading=True,
                               name=f"קלסר לדוגמה · עמודה {s['col']}, חלל {s['space']}",
                               showlegend=False, hoverinfo='name'))
    st.plotly_chart(fig, use_container_width=True, key='binder_preview')
    st.caption('ירוק: קלסר לדוגמה בחלל מתאים. לכל חלל מוצג קלסר אחד בלבד. התכנון ורשימת החיתוך אינם משתנים. מרווח ההכנסה נוסף פעם אחת לכל ממד; מוט תלייה נחשב לחסימה שמרנית לכל העומק. אין בדיקת עומס, פרזול או פתיחת דלתות.')
