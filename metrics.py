"""All Fresh Bus calculations live here. The app only draws what this file returns.

Keeping the maths separate means every number can be checked without running the app.
Targets and thresholds are set at the top so they are easy to change.
"""

from __future__ import annotations

from urllib.parse import quote

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# Targets and thresholds (edit these to change what counts as good or bad)
# --------------------------------------------------------------------------
SEATS_EXCESS = 85.0        # occupancy % at or above this = excess demand
SEATS_LOW = 70.0           # occupancy % below this = low occupancy
ON_TIME_MIN = 15           # a trip is on time if it arrives within this many minutes
LATE_ROUTE_MIN = 15.0      # a route is "late" if its average arrival delay is above this
LOW_RATING = 3.5           # a trip or route below this rating is poorly rated
EXTRA_TRIP_LOAD = 30       # seats assumed sold on a new extra departure (75% of 40)
PROMOTER_MIN = 4.5         # NPS proxy (from ratings): a trip rated this or higher counts as a promoter
DETRACTOR_BELOW = 3.5      # NPS proxy (from ratings): a trip rated below this counts as a detractor

TARGETS = {
    "margin_pct": 65.0,
    "occupancy_pct": 80.0,
    "on_time_pct": 90.0,
    "avg_rating": 4.5,
    "breakdown_rate_pct": 0.0,
    "cancel_pct": 1.0,
    "avg_dep_delay_min": 5.0,
    "avg_arr_delay_min": 10.0,
    "nps_style": 50.0,
}

REQUIRED_COLUMNS = [
    "Trip_ID", "Trip_Date", "Route", "Bus_ID", "Seats_Capacity", "Seats_Sold",
    "Revenue_INR", "Fuel_Cost_INR", "Toll_Cost_INR", "Crew_Cost_INR",
    "Departure_Delay_Mins", "Arrival_Delay_Mins", "Cancelled", "Breakdown",
    "Customer_Rating",
]

REPORT_TO = "udbhav@freshbus.com"

# Which state each city is in. Used for the region filters. Add new cities here.
CITY_STATE = {
    "Bangalore": "Karnataka", "Bengaluru": "Karnataka", "Mysore": "Karnataka", "Mangalore": "Karnataka",
    "Hyderabad": "Telangana", "Warangal": "Telangana",
    "Chennai": "Tamil Nadu", "Coimbatore": "Tamil Nadu", "Madurai": "Tamil Nadu", "Trichy": "Tamil Nadu",
    "Vijayawada": "Andhra Pradesh", "Tirupati": "Andhra Pradesh", "Visakhapatnam": "Andhra Pradesh",
    "Kochi": "Kerala", "Trivandrum": "Kerala", "Pune": "Maharashtra", "Mumbai": "Maharashtra", "Goa": "Goa",
}


# --------------------------------------------------------------------------
# Loading and cleaning
# --------------------------------------------------------------------------
def missing_columns(df: pd.DataFrame) -> list[str]:
    cols = {c.strip() for c in df.columns}
    return [c for c in REQUIRED_COLUMNS if c not in cols]


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Standardise types and add the derived columns every view uses."""
    df = raw.copy()
    df.columns = [c.strip() for c in df.columns]
    df["Trip_Date"] = pd.to_datetime(df["Trip_Date"], errors="coerce").dt.normalize()
    num = ["Seats_Capacity", "Seats_Sold", "Revenue_INR", "Fuel_Cost_INR", "Toll_Cost_INR",
           "Crew_Cost_INR", "Departure_Delay_Mins", "Arrival_Delay_Mins", "Customer_Rating"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["Cancelled", "Breakdown"]:
        df[c] = df[c].astype(str).str.strip().str.lower().isin(["yes", "y", "true", "1"])
    for c in ["Route", "Bus_ID", "Trip_ID"]:
        df[c] = df[c].astype(str).str.strip()
    df = df.dropna(subset=["Trip_Date", "Route"])

    df["Cost_INR"] = df[["Fuel_Cost_INR", "Toll_Cost_INR", "Crew_Cost_INR"]].fillna(0).sum(axis=1)
    df["Profit_INR"] = df["Revenue_INR"].fillna(0) - df["Cost_INR"]
    df["Occupancy_pct"] = 100 * df["Seats_Sold"] / df["Seats_Capacity"]
    df["Fare_INR"] = df["Revenue_INR"] / df["Seats_Sold"].replace(0, np.nan)
    df["On_Time"] = df["Arrival_Delay_Mins"] <= ON_TIME_MIN
    df["Road_Delay_Mins"] = df["Arrival_Delay_Mins"] - df["Departure_Delay_Mins"]

    # Region fields. The data has no region column, so these come from the route name
    # ("Origin-Destination") and the state each city is in.
    ends = df["Route"].str.split("-", n=1, expand=True).reindex(columns=[0, 1])
    df["Origin"] = ends[0].fillna("").str.strip()
    df["Destination"] = ends[1].fillna("").str.strip()
    df["Origin state"] = df["Origin"].map(CITY_STATE).fillna("Other")
    df["Destination state"] = df["Destination"].map(CITY_STATE).fillna("Other")
    df["Interstate"] = df["Origin state"] != df["Destination state"]
    return df.sort_values(["Trip_Date", "Trip_ID"]).reset_index(drop=True)


def operated(df: pd.DataFrame) -> pd.DataFrame:
    """Trips that actually ran. Occupancy, delay and rating are measured on these only."""
    return df[~df["Cancelled"]]


# --------------------------------------------------------------------------
# Network headline numbers
# --------------------------------------------------------------------------
def network_kpis(df: pd.DataFrame) -> dict:
    ran = operated(df)
    n_sched, n_ran = len(df), len(ran)
    rev, cost = df["Revenue_INR"].sum(), df["Cost_INR"].sum()
    seats_offered = ran["Seats_Capacity"].sum()
    seats_sold = ran["Seats_Sold"].sum()
    rated = ran["Customer_Rating"].dropna()
    late = ran[ran["Arrival_Delay_Mins"] > ON_TIME_MIN]["Customer_Rating"].dropna()

    def pct(part, whole):
        return 100 * part / whole if whole else np.nan

    return {
        "first_date": df["Trip_Date"].min(),
        "last_date": df["Trip_Date"].max(),
        "days": df["Trip_Date"].nunique(),
        "trips": n_sched,
        "routes": df["Route"].nunique(),
        "buses": df["Bus_ID"].nunique(),
        "revenue": rev,
        "cost": cost,
        "profit": rev - cost,
        "margin_pct": pct(rev - cost, rev),
        "seats_sold": seats_sold,
        "occupancy_pct": pct(seats_sold, seats_offered),
        "rev_per_seat_offered": rev / seats_offered if seats_offered else np.nan,
        "cost_per_seat_offered": cost / seats_offered if seats_offered else np.nan,
        "avg_fare": rev / seats_sold if seats_sold else np.nan,
        "profit_per_trip": (rev - cost) / n_ran if n_ran else np.nan,
        "on_time_pct": pct(ran["On_Time"].sum(), n_ran),
        "avg_dep_delay_min": ran["Departure_Delay_Mins"].mean(),
        "avg_arr_delay_min": ran["Arrival_Delay_Mins"].mean(),
        "breakdowns": int(ran["Breakdown"].sum()),
        "breakdown_rate_pct": pct(ran["Breakdown"].sum(), n_ran),
        "cancellations": int(df["Cancelled"].sum()),
        "cancel_pct": pct(df["Cancelled"].sum(), n_sched),
        "avg_rating": rated.mean() if len(rated) else np.nan,
        "low_rated_trips_pct": pct((rated < LOW_RATING).sum(), len(rated)),
        "rating_late_trips": late.mean() if len(late) else np.nan,
        "full_trips_pct": pct((ran["Occupancy_pct"] >= SEATS_EXCESS).sum(), n_ran),
        "empty_trips_pct": pct((ran["Occupancy_pct"] < 60).sum(), n_ran),
        "promoters_pct": pct((rated >= PROMOTER_MIN).sum(), len(rated)),
        "detractors_pct": pct((rated < DETRACTOR_BELOW).sum(), len(rated)),
        "nps_style": nps_style(rated),
    }


def nps_style(ratings: pd.Series) -> float:
    """NPS proxy from star ratings, not survey responses: % rated 4.5+ minus % rated below 3.5 (range -100 to +100)."""
    r = ratings.dropna()
    if not len(r):
        return np.nan
    return 100 * ((r >= PROMOTER_MIN).mean() - (r < DETRACTOR_BELOW).mean())


# --------------------------------------------------------------------------
# Route scorecard
# --------------------------------------------------------------------------
def _action(occ: float, reliable: bool) -> str:
    if occ >= SEATS_EXCESS and reliable:
        return "Add capacity"
    if occ < SEATS_LOW and not reliable:
        return "Fix reliability, then demand"
    if occ < SEATS_LOW:
        return "Grow demand"
    if not reliable:
        return "Fix reliability"
    return "Hold"


def route_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for route, g in df.groupby("Route"):
        ran = operated(g)
        rev, cost = g["Revenue_INR"].sum(), g["Cost_INR"].sum()
        offered, sold = ran["Seats_Capacity"].sum(), ran["Seats_Sold"].sum()
        occ = 100 * sold / offered if offered else np.nan
        arr = ran["Arrival_Delay_Mins"].mean()
        bd = int(ran["Breakdown"].sum())
        reliable = (arr <= LATE_ROUTE_MIN) and bd == 0
        rows.append({
            "Route": route,
            "Trips": len(g),
            "Revenue": rev,
            "Cost": cost,
            "Profit": rev - cost,
            "Margin %": 100 * (rev - cost) / rev if rev else np.nan,
            "Profit per trip": (rev - cost) / len(ran) if len(ran) else np.nan,
            "Seats sold": sold,
            "Occupancy %": occ,
            "Lowest trip occupancy %": ran["Occupancy_pct"].min(),
            "Avg fare": rev / sold if sold else np.nan,
            "Cost per trip": cost / len(ran) if len(ran) else np.nan,
            "Departure delay (min)": ran["Departure_Delay_Mins"].mean(),
            "Arrival delay (min)": arr,
            "Delay added on road (min)": ran["Road_Delay_Mins"].mean(),
            "Worst arrival delay (min)": ran["Arrival_Delay_Mins"].max(),
            "On-time %": 100 * ran["On_Time"].mean() if len(ran) else np.nan,
            "Breakdowns": bd,
            "Breakdown rate %": 100 * bd / len(ran) if len(ran) else np.nan,
            "Cancelled": int(g["Cancelled"].sum()),
            "Cancellation %": 100 * g["Cancelled"].mean(),
            "Rating": ran["Customer_Rating"].mean(),
            "NPS proxy": nps_style(ran["Customer_Rating"]),
            "Demand": ("Excess demand" if occ >= SEATS_EXCESS
                       else "Low occupancy" if occ < SEATS_LOW else "Healthy"),
            "Reliable": reliable,
            "Action": _action(occ, reliable),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["Revenue share %"] = 100 * out["Revenue"] / out["Revenue"].sum()
    return out.sort_values("Revenue", ascending=False).reset_index(drop=True)


def capacity_case(routes: pd.DataFrame, load: int = EXTRA_TRIP_LOAD) -> pd.DataFrame:
    """Profit from one extra daily departure on routes already running 85%+ full.

    `load` is the number of seats we assume the new departure sells.
    """
    full = routes[routes["Occupancy %"] >= SEATS_EXCESS].copy()
    if full.empty:
        return full
    full["Break-even seats"] = np.ceil(full["Cost per trip"] / full["Avg fare"])
    full["Profit per extra trip"] = load * full["Avg fare"] - full["Cost per trip"]
    full["Monthly upside (30 days)"] = 30 * full["Profit per extra trip"]
    cols = ["Route", "Occupancy %", "Avg fare", "Cost per trip", "Break-even seats",
            "Profit per extra trip", "Monthly upside (30 days)"]
    # Ranked by the extra profit a new departure would earn, so the top row is the first route to add a bus to
    return full[cols].sort_values("Monthly upside (30 days)", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Operations and customer views
# --------------------------------------------------------------------------
def bus_table(df: pd.DataFrame) -> pd.DataFrame:
    ran = operated(df)
    if ran.empty:
        return pd.DataFrame()
    g = ran.groupby("Bus_ID").agg(
        Route=("Route", "first"),
        Trips=("Trip_ID", "count"),
        Breakdowns=("Breakdown", "sum"),
        **{"Avg arrival delay (min)": ("Arrival_Delay_Mins", "mean"),
           "Avg rating": ("Customer_Rating", "mean")},
    ).reset_index().rename(columns={"Bus_ID": "Bus"})
    g["Breakdowns"] = g["Breakdowns"].astype(int)
    g["Breakdown rate %"] = 100 * g["Breakdowns"] / g["Trips"]
    return g.sort_values(["Breakdowns", "Avg arrival delay (min)"], ascending=False).reset_index(drop=True)


def breakdown_effect(df: pd.DataFrame) -> pd.DataFrame:
    ran = operated(df)
    rows = []
    for label, flag in [("With a breakdown", True), ("Without a breakdown", False)]:
        g = ran[ran["Breakdown"] == flag]
        if len(g):
            rows.append({"Trips": label, "Count": len(g),
                         "Avg arrival delay (min)": g["Arrival_Delay_Mins"].mean(),
                         "Avg rating": g["Customer_Rating"].mean()})
    return pd.DataFrame(rows)


DRIVERS = {
    "Arrival delay": "Arrival_Delay_Mins",
    "Departure delay": "Departure_Delay_Mins",
    "Delay added on road": "Road_Delay_Mins",
    "Breakdown on trip": "Breakdown",
    "Seat occupancy": "Occupancy_pct",
    "Fare paid": "Fare_INR",
}


def rating_drivers(df: pd.DataFrame) -> pd.DataFrame:
    """Correlation of each trip metric with customer rating. Needs at least 4 rated trips."""
    ran = operated(df).dropna(subset=["Customer_Rating"])
    if len(ran) < 4 or ran["Customer_Rating"].nunique() < 2:
        return pd.DataFrame(columns=["Metric", "Correlation", "Strength"])
    rows = []
    for name, col in DRIVERS.items():
        x = ran[col].astype(float)
        if x.nunique() < 2:
            continue
        r = float(np.corrcoef(x, ran["Customer_Rating"])[0, 1])
        strength = "Strong" if abs(r) >= 0.7 else "Moderate" if abs(r) >= 0.4 else "Weak"
        rows.append({"Metric": name, "Correlation": r, "Strength": strength})
    return pd.DataFrame(rows).sort_values("Correlation").reset_index(drop=True)


def delay_rating_slope(df: pd.DataFrame) -> tuple[float, float] | None:
    """Least-squares line of rating on arrival delay: (slope per minute, intercept)."""
    ran = operated(df).dropna(subset=["Customer_Rating", "Arrival_Delay_Mins"])
    if len(ran) < 3 or ran["Arrival_Delay_Mins"].nunique() < 2:
        return None
    slope, intercept = np.polyfit(ran["Arrival_Delay_Mins"], ran["Customer_Rating"], 1)
    return float(slope), float(intercept)


def daily_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    rows = []
    for day, g in df.groupby("Trip_Date"):
        ran = operated(g)
        rows.append({
            "Date": day,
            "Revenue": g["Revenue_INR"].sum(),
            "Profit": g["Profit_INR"].sum(),
            "Occupancy %": 100 * ran["Seats_Sold"].sum() / ran["Seats_Capacity"].sum() if len(ran) else np.nan,
            "Avg arrival delay (min)": ran["Arrival_Delay_Mins"].mean(),
            "Avg rating": ran["Customer_Rating"].mean(),
            "Breakdowns": int(ran["Breakdown"].sum()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Status against target (used for the coloured chips)
# --------------------------------------------------------------------------
def status(metric: str, value: float) -> str:
    """Return 'good', 'watch' or 'bad' for a headline metric against its target."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "na"
    t = TARGETS[metric]
    lower_is_better = metric in {"breakdown_rate_pct", "cancel_pct", "avg_dep_delay_min", "avg_arr_delay_min"}
    if lower_is_better:
        if value <= t:
            return "good"
        slack = max(t, 1) * 1.0 if metric.endswith("_min") else 5
        return "watch" if value <= t + slack else "bad"
    if value >= t:
        return "good"
    slack = 0.3 if metric == "avg_rating" else 25 if metric == "nps_style" else 10
    return "watch" if value >= t - slack else "bad"


# --------------------------------------------------------------------------
# Formatting helpers (Indian number style)
# --------------------------------------------------------------------------
def inr(x: float) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    neg, x = x < 0, abs(round(x))
    s = str(int(x))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-₹" if neg else "₹") + s


def inr_short(x: float) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return inr(x)


def pct(x: float, d: int = 1) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.{d}f}%"


def mins(x: float) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.1f} min"


def num(x: float, d: int = 2) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:.{d}f}"


def nice_date(d) -> str:
    t = pd.Timestamp(d)
    return f"{t.day} {t:%b %Y}"


# --------------------------------------------------------------------------
# Weekly business review report
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Action plan and CEO brief (shared by the dashboard and the email)
# --------------------------------------------------------------------------
def review_date(last_date) -> pd.Timestamp:
    """The Monday review that follows the last day of data."""
    d = pd.Timestamp(last_date).normalize()
    return d + pd.Timedelta(days=(7 - d.weekday()) % 7 or 7)


def short_date(t) -> str:
    t = pd.Timestamp(t)
    return f"{t:%a} {t.day} {t:%b}"


def next_review_on_or_after(d) -> pd.Timestamp:
    d = pd.Timestamp(d).normalize()
    return d + pd.Timedelta(days=(7 - d.weekday()) % 7)


def action_plan(df: pd.DataFrame) -> list[dict]:
    """This week's actions, in priority order, with the problem, owner, due date, success measure and review date."""
    k = network_kpis(df)
    routes = route_table(df)
    buses = bus_table(df)
    cap = capacity_case(routes)
    fix = routes[~routes["Action"].isin(["Add capacity", "Hold"])].sort_values("Profit per trip")
    bad_bus = buses[buses["Breakdowns"] >= 2] if not buses.empty else buses
    mon = review_date(k["last_date"])
    plan = []
    if not bad_bus.empty:
        ids = bad_bus["Bus"].tolist()
        n_bd = int(bad_bus["Breakdowns"].sum())
        plan.append(dict(
            priority="P1",
            problem=(f"{' and '.join(ids)} broke down on {n_bd} of {int(bad_bus['Trips'].sum())} trips, "
                     f"{n_bd} of the network's {k['breakdowns']} breakdowns"),
            action=f"Inspect {' and '.join(ids)} (battery, drivetrain, charging logs); run healthy buses until cleared",
            owner="Operations Head", due=mon + pd.Timedelta(days=2),
            measure="Zero breakdowns on these buses for 4 weeks",
            impact=f"Removes {n_bd} of {k['breakdowns']} breakdowns",
            why=f"Together they caused {n_bd} of the {k['breakdowns']} breakdowns, breaking down on every trip they ran",
            decision=f"Take {' and '.join(ids)} off the road for inspection"))
    if not fix.empty:
        f2 = fix.head(2)
        names = f2["Route"].tolist()
        plan.append(dict(
            priority="P1",
            problem=(f"{' and '.join(names)} arrive {f2['Arrival delay (min)'].min():.0f} to {f2['Arrival delay (min)'].max():.0f} min late; "
                     f"most of it starts before departure ({f2['Departure delay (min)'].min():.0f} to {f2['Departure delay (min)'].max():.0f} min)"),
            action="Departure-discipline drive: boarding cut-off, earlier crew reporting, charge-ready check the night before",
            owner="Operations Head", due=mon + pd.Timedelta(days=7),
            measure="Departure delay under 5 min; on-time arrival above 80% on these routes",
            impact="Each 10 min saved is worth about half a star in rating",
            why=(f"They arrive {f2['Arrival delay (min)'].min():.0f} to {f2['Arrival delay (min)'].max():.0f} min late, and "
                 f"{f2['Departure delay (min)'].min():.0f} to {f2['Departure delay (min)'].max():.0f} min of that happens before the bus leaves. "
                 "That part is fully in our control"),
            decision=f"Back an on-time push on {' and '.join(names)}"))
    if not cap.empty:
        c = cap.iloc[0]
        r = routes[routes["Route"] == c["Route"]].iloc[0]
        plan.append(dict(
            priority="P2",
            problem=f"{c['Route']} runs {pct(r['Occupancy %'], 0)} full and on time, so riders are likely being turned away",
            action=(f"Pilot one extra daily departure on {c['Route']} for 4 weeks, after confirming sold-out dates and a spare bus. "
                    f"Costs {inr(c['Cost per trip'])} a trip; breaks even at {c['Break-even seats']:.0f} of 40 seats"),
            owner="Revenue Head", due=mon + pd.Timedelta(days=7),
            measure="New trip 75%+ full; existing trips stay 85%+",
            impact=f"About {inr_short(c['Monthly upside (30 days)'])} extra profit over 30 days (projection)",
            why=(f"It runs {pct(r['Occupancy %'], 0)} full and on time. An extra trip breaks even at {c['Break-even seats']:.0f} of 40 seats "
                 f"and adds about {inr_short(c['Monthly upside (30 days)'])} over 30 days if it sells 30"),
            decision=f"Approve a 4-week pilot departure on {c['Route']}"))
    if not fix.empty:
        w = fix.iloc[0]
        plan.append(dict(
            priority="P2",
            problem=f"{w['Route']} earns {inr(w['Profit per trip'])} a trip vs {inr(k['profit_per_trip'])} network average, at {pct(w['Occupancy %'], 0)} full",
            action=f"Hold paid demand campaigns on {w['Route']} until punctuality is fixed; restart after the 4-week check",
            owner="CEO", due=mon + pd.Timedelta(days=28),
            measure="Occupancy above 70% after the reliability fix",
            impact="Avoids spending to attract riders to a late service",
            decision=None))
    plan.append(dict(
        priority="P3",
        problem="Satisfaction is tracked only through star ratings; no survey NPS or complaint reasons",
        action="Add a one-question NPS survey and complaint reasons to the post-trip message",
        owner="CX lead", due=mon + pd.Timedelta(days=14),
        measure="Survey NPS captured on 50%+ of trips",
        impact="Replaces the NPS proxy with real NPS and shows what to fix",
        decision=None))
    for p in plan:
        p["status"] = "Not started"
        p["next_review"] = next_review_on_or_after(p["due"])
    return plan


def key_findings(df: pd.DataFrame) -> list[dict]:
    """One headline finding per Part A area, with the number behind it."""
    k = network_kpis(df)
    routes = route_table(df)
    buses = bus_table(df)
    slope = delay_rating_slope(df)
    out = []
    top = routes.head(3)
    best = routes.sort_values("Profit", ascending=False).iloc[0]
    out.append(dict(area="Revenue", headline=(
        f"{'The top ' + str(len(top)) + ' routes bring' if len(top) > 1 else 'This route brings'} {pct(top['Revenue'].sum() / max(k['revenue'], 1) * 100, 0)} of revenue and "
        f"{pct(top['Profit'].sum() / max(k['profit'], 1) * 100, 0)} of contribution profit."),
        detail=f"{best['Route']} keeps the most: {inr_short(best['Profit'])} at {pct(best['Margin %'], 0)} margin."))
    full = routes[routes["Occupancy %"] >= SEATS_EXCESS]
    low = routes[routes["Occupancy %"] < SEATS_LOW]
    dem = []
    if not full.empty:
        dem.append(f"{len(full)} route{'s' if len(full) != 1 else ''} {'run' if len(full) != 1 else 'runs'} "
                   f"{pct(full['Occupancy %'].min(), 0)} to {pct(full['Occupancy %'].max(), 0)} full")
    if not low.empty:
        dem.append(f"{len(low)} {'run' if len(low) != 1 else 'runs'} {pct(low['Occupancy %'].min(), 0)} to {pct(low['Occupancy %'].max(), 0)} full")
    out.append(dict(area="Demand", headline=("; ".join(dem) + ".") if dem else f"Network occupancy is {pct(k['occupancy_pct'], 0)}.",
                    detail="Full routes are the reliable ones, so supply follows service quality."))
    share = (100 * k["avg_dep_delay_min"] / k["avg_arr_delay_min"]
             if k["avg_arr_delay_min"] and k["avg_arr_delay_min"] > 0 and k["avg_dep_delay_min"] >= 0 else np.nan)
    share = min(share, 100) if not np.isnan(share) else share
    bd_bus = buses[buses["Breakdowns"] >= 2] if not buses.empty else buses
    ops_detail = (f"{int(bd_bus['Breakdowns'].sum())} of {k['breakdowns']} breakdowns sit on {len(bd_bus)} buses. "
                  if not bd_bus.empty else f"{k['breakdowns']} breakdowns. ") + ("No cancellations in the period." if k["cancellations"] == 0 else f"{k['cancellations']} cancellations.")
    out.append(dict(area="Operations", headline=(
        f"{pct(k['on_time_pct'], 0)} of trips arrive on time. About {pct(share, 0)} of the delay starts before departure."
        if not np.isnan(share) else f"{pct(k['on_time_pct'], 0)} of trips arrive on time."), detail=ops_detail))
    cx = (f"Each 10 min late goes with about {abs(slope[0]) * 10:.1f} stars lower. " if slope else "")
    out.append(dict(area="Customer", headline=cx + f"Average rating {num(k['avg_rating'])}.",
                    detail=(f"NPS proxy by route ranges from {nps_style_str(routes['NPS proxy'].max())} to "
                            f"{nps_style_str(routes['NPS proxy'].min())}.")))
    return out


def ceo_brief(df: pd.DataFrame) -> dict:
    routes = route_table(df)
    scale = routes[routes["Action"] == "Add capacity"].sort_values("Occupancy %", ascending=False)
    fix = routes[~routes["Action"].isin(["Add capacity", "Hold"])].sort_values("Profit per trip")
    if not scale.empty:
        win = (f"{len(scale)} route{'s' if len(scale) != 1 else ''} ({', '.join(scale['Route'])}) "
               f"{'runs' if len(scale) == 1 else 'run'} {pct(scale['Occupancy %'].min(), 0)} to {pct(scale['Occupancy %'].max(), 0)} full "
               f"at {pct(scale['Margin %'].min(), 0)} to {pct(scale['Margin %'].max(), 0)} margin, on time and well rated.")
    else:
        top = routes.sort_values("Profit", ascending=False).iloc[0]
        win = f"{top['Route']} leads on profit at {inr_short(top['Profit'])} ({pct(top['Margin %'], 0)} margin)."
    if not fix.empty:
        w = fix.iloc[0]
        watch = (f"{w['Route']}: {pct(w['Occupancy %'], 0)} full, {mins(w['Arrival delay (min)'])} late on average, "
                 f"rating {num(w['Rating'])}. A reliability fix should lift both ratings and demand.")
    else:
        watch = "No route is off target on both demand and reliability this week."
    decisions = [p["decision"] for p in action_plan(df) if p.get("decision")][:3]
    return dict(win=win, decisions=decisions, watch=watch)


def short_period(a, b) -> str:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    if a == b:
        return f"{a.day} {a:%b %Y}"
    if (a.month, a.year) == (b.month, b.year):
        return f"{a.day} to {b.day} {b:%b %Y}"
    return f"{a.day} {a:%b} to {b.day} {b:%b %Y}"


def build_report(df: pd.DataFrame, sender: str = "Abhigya Asmi Pandey", dashboard_url: str = "") -> tuple[str, str]:
    """Weekly review email: short, plain and decision-first."""
    k = network_kpis(df)
    routes = route_table(df)
    slope = delay_rating_slope(df)
    plan = action_plan(df)
    decisions = [p for p in plan if p.get("decision")]
    others = [p for p in plan if not p.get("decision")]
    period = short_period(k["first_date"], k["last_date"])
    n_dec = len(decisions)
    subject = f"Fresh Bus weekly review, {period}" + (f": {n_dec} decision{'s' if n_dec != 1 else ''} needed" if n_dec else "")

    scale = routes[routes["Action"] == "Add capacity"].sort_values("Occupancy %", ascending=False)
    fix = routes[~routes["Action"].isin(["Add capacity", "Hold"])].sort_values("Profit per trip")
    hold = routes[routes["Action"] == "Hold"]

    def vs(value: str, target: str) -> str:
        return f"{value} (target {target})"

    # The short version: three plain sentences
    short = [f"{'Profit is healthy' if k['margin_pct'] >= 55 else 'Profit needs attention'}: {inr_short(k['profit'])} on "
             f"{inr_short(k['revenue'])} revenue, a {pct(k['margin_pct'], 0)} margin."]
    if k["on_time_pct"] < TARGETS["on_time_pct"]:
        line = f"Punctuality is the main problem: only {pct(k['on_time_pct'], 0)} of trips arrived on time"
        line += (f", and each 10 minutes late costs about {abs(slope[0]) * 10:.1f} stars in rating." if slope else ".")
        short.append(line)
    if not scale.empty:
        short.append(f"{len(scale)} route{'s are' if len(scale) != 1 else ' is'} full and on time, and can take more buses.")

    L = ["Hi Udbhav,", "", f"Here is the weekly review for {period} ({k['trips']} trips, {k['routes']} route{'s' if k['routes'] != 1 else ''}).", "",
         "THE SHORT VERSION"]
    L += [f"- {x}" for x in short]

    L += ["", "NUMBERS VS TARGET",
          f"- Revenue: {inr_short(k['revenue'])}",
          f"- Contribution margin: {vs(pct(k['margin_pct']), '65%')}",
          f"- Seats sold: {vs(pct(k['occupancy_pct']), '80%')}",
          f"- On-time arrivals: {vs(pct(k['on_time_pct']), '90%')}",
          f"- Average rating: {vs(num(k['avg_rating']), '4.5')}",
          "- Breakdowns: " + vs(f"{k['breakdowns']} of {k['trips']} trips", "0"),
          f"- Cancellations: {k['cancellations']}"]

    L += ["", "ROUTES"]
    if not scale.empty:
        L.append("Ready to grow: " + "; ".join(
            f"{r['Route']} ({pct(r['Occupancy %'], 0)} full, rated {num(r['Rating'], 1)})" for _, r in scale.iterrows()) + ".")
    if not fix.empty:
        L.append("Need fixing: " + "; ".join(
            f"{r['Route']} ({pct(r['Occupancy %'], 0)} full, {r['Arrival delay (min)']:.0f} min late, "
            + (f"{r['Breakdowns']} breakdown{'s' if r['Breakdowns'] != 1 else ''}, " if r['Breakdowns'] else "") + f"rated {num(r['Rating'], 1)})" for _, r in fix.iterrows()) + ".")
    if not hold.empty:
        L.append("Steady: " + ", ".join(hold["Route"]) + ".")

    if decisions:
        L += ["", "DECISIONS NEEDED FROM YOU"]
        for i, p in enumerate(decisions, 1):
            L.append(f"{i}. {p['decision']}.")
            L.append(f"   Why: {p.get('why', p['problem'])}.")
            L.append(f"   Owner: {p['owner']}, by {short_date(p['due'])}. Success: {p['measure']}.")
    if others:
        L += ["", "ALSO IN PROGRESS"]
        for p in others:
            L.append(f"- {p['action']} ({p['owner']}, by {short_date(p['due'])}).")

    L += ["", "NOTES",
          f"- {k['days']} days of data, so treat these as early signals. Trends firm up as weeks are added.",
          f"- NPS proxy from star ratings is {nps_style_str(k['nps_style'])}. It is not survey NPS.",
          "- Profit is before fixed costs such as bus lease, depot and charging set-up."]
    if dashboard_url:
        L += ["", f"Full dashboard: {dashboard_url}"]
    L += ["", "Thanks,", sender]
    return subject, "\n".join(L)


def nps_style_str(x) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:+.0f}"


def mailto_link(subject: str, body: str, to: str = REPORT_TO) -> str:
    return f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"


def gmail_link(subject: str, body: str, to: str = REPORT_TO) -> str:
    return (f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(to)}"
            f"&su={quote(subject)}&body={quote(body)}")
