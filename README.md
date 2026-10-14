# Fresh Bus route performance dashboard

An interactive dashboard for Fresh Bus's trip data. It answers each question in the
Program Manager assignment in plain words, shows a chart for each, sets out the KPI
framework, and emails the weekly business review to udbhav@freshbus.com in one click.

## What's inside

| File | What it does |
|---|---|
| `app.py` | The dashboard page: layout, charts, buttons |
| `metrics.py` | Every calculation. Targets and thresholds are at the top |
| `data/freshbus_trips.csv` | Saved copy of the trip data (used if the Google Sheet can't be reached) |
| `requirements.txt` | The Python packages the app needs |
| `.streamlit/config.toml` | Colours and theme |
| `.streamlit/secrets.toml.example` | Optional settings for the "Send now" email button |

## How the dashboard is organised

- **Header:** the dashboard name, the week covered, how many trips, routes and buses, and where the data comes from.
- **Bottom line:** the week in two sentences.
- **Network scorecard:** six headline numbers for the selected period, each with a plain definition and its status against a proposed target.
- **Tabs:** Overview (route portfolio map, route scorecard, action plan), then one tab per assignment area: Revenue, Demand and capacity, Operations, Customer experience, KPI framework and Weekly review.
- **Each question** shows the finding, the action I would take as Program Manager, and one chart chosen to answer it.

## Controls

- **Display:** dark (default) or light, at the top of the sidebar. Light suits projectors and printing.
- **Filters:** date range, region (state), starting city, routes, bus, and trips with or without a breakdown. Leave a box empty to include everything.
- **Scenario slider** on the Demand and capacity tab: test how many seats an extra daily departure must sell.
- **Weekly report:** email it to udbhav@freshbus.com from the sidebar or the Weekly review tab.

Regions come from the city names in each route (for example, Bangalore-Chennai serves Karnataka and Tamil Nadu). To add a city, add it to `CITY_STATE` in `metrics.py`.

## Put it online for free (about 10 minutes, no coding)

1. **Create a GitHub account** at github.com if you don't have one.
2. **Make a new repository.** Click **+** (top right), then **New repository**. Name it
   `freshbus-dashboard`, choose **Public**, and click **Create repository**.
3. **Upload the files.** Click **uploading an existing file**. Drag in `app.py`, `metrics.py`,
   `requirements.txt` and `README.md`. Click **Commit changes**.
4. **Add the data folder.** Click **Add file > Upload files**. Drag in the whole `data` folder.
   Commit.
5. **Add the theme file.** Hidden folders often don't upload by dragging, so create it by hand:
   **Add file > Create new file**, type `.streamlit/config.toml` as the name, paste in the
   contents of `config.toml` from this folder, and commit.
6. **Deploy.** Go to share.streamlit.io and sign in with GitHub. Click **Create app**, then
   **Deploy a public app from GitHub**. Choose your repository, branch `main`, main file `app.py`.
   Open **Advanced settings**, pick **Python 3.12**, then click **Deploy**.
7. After a minute or two you get a link like `https://freshbus-dashboard.streamlit.app`.
   Anyone with the link can open it.

### Optional extras

- **Add your link to the report:** in Streamlit Cloud open your app's **Settings > Secrets**
  and paste the `[app]` section from `secrets.toml.example` with your real link.
- **"Send now" button:** paste the `[smtp]` section too, with a Gmail app password. The
  dashboard can then send the report without opening an email app.

## Run it on your own computer

**Windows (easiest):** double-click `run_dashboard.bat`. It installs Streamlit the first time, then opens the dashboard in your browser at http://localhost:8501. Keep the black window open while you use it.

**Any computer:**

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Where the data comes from

The app first reads the live Raw_Data Google Sheet (it must be shared as "anyone with the
link"). If that fails, it uses `data/freshbus_trips.csv`. For a new week, use
**Upload a new week's data** in the sidebar. The file needs the same columns as the sheet.

## How the main numbers are worked out

- **Contribution profit** = revenue − fuel − toll − crew. It excludes depreciation,
  maintenance, GST and overheads.
- **Seat occupancy** = seats sold ÷ seats offered, on trips that ran.
- **On time** = arrived within 15 minutes of schedule.
- **Excess demand** = 85%+ of seats sold. **Low occupancy** = under 70%.
- **Recommended action:** a route that is 85%+ full and reliable (under 15 min late on
  average, no breakdowns) gets *Add capacity*. Under 70% full and unreliable gets
  *Fix reliability, then demand*.
- **Correlation** runs from −1 to +1 and shows how closely two things move together across trips.
- Customer rating stands in for NPS, because the data has no NPS field.
