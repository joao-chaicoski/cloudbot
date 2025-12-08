# Cloudbot — Transaction Analytics Agent

**Repository layout**
- `main.py` — Streamlit app UI
- `agent.py` — LLM prompt + query runner (returns SQL and pandas DataFrame)
- `kpis.py` - 
- `db/init_db.py` — helper to create `cloudwalk.db` from CSV
- `data/operational_intelligence_transactions_db.csv` — sample data
- `requirements.txt` — Python dependencies

**Prerequisites**
- Python 3.9+ (3.10/3.11 recommended)
- (Windows) PowerShell is used in examples

Quick setup

1. Clone or open this folder in your terminal.

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
& '.\.venv\Scripts\Activate.ps1'
```

3. Install dependencies:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

4. Create the DuckDB database from the CSV (reads `data/operational_intelligence_transactions_db.csv` with `;` separator):

```powershell
.\.venv\Scripts\python db\init_db.py
```

5. Set up the LLM

- First you need to get an API Key at - https://console.groq.com/keys

- To enable the model to generate SQL, set your GROQ API key in a `.env` file at the repository root:

```
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile (this is the default model if you don't set any other specific model to run.)
```

6. Run the app
Start Streamlit using the project's venv Python so it uses the same environment:

```powershell
.\.venv\Scripts\python -m streamlit run main.py
```

Or activate the venv (if not activated already) then run:

```powershell
& '.\.venv\Scripts\Activate.ps1'
streamlit run main.py
```

Usage

- In the app input box you can either:
  - Type a natural language question (e.g., "What is the total amount by entity?") — this will call the configured GROQ model to produce SQL, execute it, and display results and charts.
  
- You can change between Bar Chart, Line Chart and Boxplot. Visuals use Seaborn/Matplotlib.



KPI tool (Daily TPV & Alerts)
-----------------------------
Streamlit UI
- Start the app as described above and open the sidebar by clicking in the top left of the screen to see "Daily KPIs & Alerts" section.
- UI controls:
  - `KPI date`: pick the date to evaluate (defaults to today when left empty).
  - `Alert threshold`: a fractional threshold (e.g., `0.25` = 25%). Set up the Lower and Upper ends of the threshold and the agent will Trigger if it see any changes that go over or under the limits.
  - `Webhook URL`: optional; if provided, you can click "Send KPI Alert" after a trigger fires.
- Click `Run KPIs` to compute TPV and view percentage variations vs D-1, D-7 and D-30. If any variation exceeds the threshold you'll see a warning and can send the alert.


Configuration and notes
- Database: `kpis.py` reads from `cloudwalk.db` by default. Set `CLOUDWALK_DB` environment variable to change the path.
- If comparative days are missing (or previous value is 0) the percent change is reported as `N/A` and will not trigger an alert.