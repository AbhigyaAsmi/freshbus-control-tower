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
PROMOTER_MIN = 4.5         # NPS-style score: a trip rated this or higher counts as a promoter
DETRACTOR_BELOW = 3.5      # NPS-style score: a trip rated below this counts as a detractor

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
    """NPS-style score from star ratings: % rated 4.5+ minus % rated below 3.5 (range -100 to +100)."""
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
            "NPS-style": nps_style(ran["Customer_Rating"]),
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


def action_plan(df: pd.DataFrame) -> list[dict]:
    """This week's actions with owner, due date and the metric each should move."""
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
        plan.append(dict(
            action=f"Inspect {' and '.join(ids)} (battery, drivetrain, charging logs) and swap in healthy buses until cleared",
            owner="Operations Head", due=mon + pd.Timedelta(days=2),
            why="; ".join(f"{r['Bus']}: {r['Breakdowns']} of {r['Trips']} trips" for _, r in bad_bus.iterrows()),
            measure="Breakdown rate to 0%", decision=f"Take {' and '.join(ids)} off the road for inspection"))
    if not cap.empty:
        c = cap.iloc[0]
        r = routes[routes["Route"] == c["Route"]].iloc[0]
        plan.append(dict(
            action=f"Pilot one extra daily departure on {c['Route']} for 4 weeks, after checking sold-out dates and a spare bus",
            owner="Revenue Head", due=mon + pd.Timedelta(days=7),
            why=(f"{pct(r['Occupancy %'], 0)} full, rating {num(r['Rating'])}. Costs {inr(c['Cost per trip'])} a trip and "
                 f"breaks even at {c['Break-even seats']:.0f} of 40 seats. At 30 seats: about {inr_short(c['Monthly upside (30 days)'])} "
                 "over 30 days (projection)"),
            measure="New trip 75%+ full; existing trips stay 85%+",
            decision=f"Approve a 4-week pilot departure on {c['Route']}"))
    if not fix.empty:
        names = fix["Route"].tolist()[:2]
        plan.append(dict(
            action=f"Departure-discipline drive on {' and '.join(names)}: boarding cut-off, earlier crew reporting, charge-ready check the night before",
            owner="Operations Head", due=mon + pd.Timedelta(days=7),
            why="Most of the delay starts before the bus leaves",
            measure="Departure delay under 5 min",
            decision=f"Back an on-time push on {' and '.join(names)}"))
        w = fix.iloc[0]
        plan.append(dict(
            action=f"Pause paid demand campaigns on {w['Route']} until punctuality is fixed; restart after the 4-week check",
            owner="CEO", due=mon + pd.Timedelta(days=28),
            why=f"Earns {inr(w['Profit per trip'])} a trip vs {inr(k['profit_per_trip'])} network average",
            measure="Occupancy above 70%", decision=None))
    plan.append(dict(
        action="Add a one-question NPS survey and complaint reasons to the post-trip message",
        owner="CX lead", due=mon + pd.Timedelta(days=14),
        why="Turns the star rating into a true NPS and tells us what to fix",
        measure="NPS captured on 50%+ of trips", decision=None))
    return plan


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


def build_report(df: pd.DataFrame, sender: str = "Abhigya Asmi Pandey", dashboard_url: str = "") -> tuple[str, str]:
    k = network_kpis(df)
    routes = route_table(df)
    buses = bus_table(df)
    cap = capacity_case(routes)
    drivers = rating_drivers(df)
    slope = delay_rating_slope(df)

    period = f"{nice_date(k['first_date'])} to {nice_date(k['last_date'])}"
    subject = f"Fresh Bus weekly business review: {period}"

    scale = routes[routes["Action"] == "Add capacity"].sort_values("Occupancy %", ascending=False)
    fix = routes[~routes["Action"].isin(["Add capacity", "Hold"])].sort_values("Profit per trip")
    bad_bus = buses[buses["Breakdowns"] >= 2]["Bus"].tolist() if not buses.empty else []

    L = [
        "Hi Udbhav,",
        "",
        f"Here is the weekly business review for {period} ({k['trips']} trips, "
        f"{k['routes']} route{'s' if k['routes'] != 1 else ''}).",
        "",
        "1. HEADLINE",
        f"Revenue: {inr(k['revenue'])}. Contribution profit: {inr(k['profit'])} ({pct(k['margin_pct'])} margin).",
        f"Seat occupancy: {pct(k['occupancy_pct'])}. On-time arrivals: {pct(k['on_time_pct'])}.",
        f"Avg rating: {num(k['avg_rating'])} of 5 (NPS-style {nps_style_str(k['nps_style'])}). Breakdowns: {k['breakdowns']} of {k['trips']} trips. "
        f"Cancellations: {k['cancellations']}.",
        "",
        "2. ROUTES TO SCALE",
    ]
    if scale.empty:
        L.append("- None this week.")
    for _, r in scale.iterrows():
        L.append(f"- {r['Route']}: {pct(r['Occupancy %'])} full, {pct(r['Margin %'])} margin, "
                 f"rating {num(r['Rating'])}.")
    L += ["", "3. ROUTES TO FIX"]
    if fix.empty:
        L.append("- None this week.")
    for _, r in fix.iterrows():
        L.append(f"- {r['Route']}: {pct(r['Occupancy %'])} full, {mins(r['Arrival delay (min)'])} late on arrival, "
                 f"{r['Breakdowns']} breakdowns, rating {num(r['Rating'])}.")
    L += ["", "4. WHAT DRIVES RATINGS"]
    if not drivers.empty:
        top = drivers.reindex(drivers["Correlation"].abs().sort_values(ascending=False).index).iloc[0]
        L.append(f"{top['Metric']} has the strongest link to rating (r = {top['Correlation']:.2f}).")
    if slope:
        L.append(f"Each extra 10 minutes of arrival delay goes with a rating about {abs(slope[0]) * 10:.2f} points lower.")
    if bad_bus:
        L.append(f"Breakdowns sit on a few buses: {', '.join(bad_bus)} broke down 2 or more times.")
    L += ["", "5. DECISIONS AND ACTIONS (owner, due)"]
    for p in action_plan(df):
        L.append(f"- {p['action']} ({p['owner']}, by {short_date(p['due'])}). Success: {p['measure']}.")
    L += [
        "",
        "6. SCOPE AND NEXT STEPS",
        f"This review covers {k['days']} days ({k['trips']} trips). The dashboard refreshes each week, "
        "so trends and week-on-week changes build up from here.",
        f"Customer view: NPS-style score {nps_style_str(k['nps_style'])} from star ratings "
        f"({PROMOTER_MIN}+ promoters, below {DETRACTOR_BELOW} detractors), until a true NPS survey is live.",
        "Profit shown is contribution profit: revenue minus energy, toll and crew cost, before fixed costs.",
    ]
    if dashboard_url:
        L += ["", f"Live dashboard: {dashboard_url}"]
    L += ["", "Regards,", sender]
    return subject, "\n".join(L)


def nps_style_str(x) -> str:
    return "n/a" if x is None or pd.isna(x) else f"{x:+.0f}"


def mailto_link(subject: str, body: str, to: str = REPORT_TO) -> str:
    return f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"


def gmail_link(subject: str, body: str, to: str = REPORT_TO) -> str:
    return (f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(to)}"
            f"&su={quote(subject)}&body={quote(body)}")
