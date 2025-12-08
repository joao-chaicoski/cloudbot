# Cloudbot — Transaction Analytics Agent
## Short Presentation
Cloudbot was created to help translate Business questions into SQL queries and visualizations. In addition to this, there is also a Daily KPIs module included to help tracking key KPIs and if they are going over or under the selected thresholds. Obs.: For now the only monitored KPI is TPV.)

Cloudbot uses a Large Language Model (Groq Llama 3). to translate Natural Language questions into queries. Allowing the uszer to "chat" with the database. With little tweaking to the code, the user is able to personalize rules for Cloudbot.

**The current architecture is as follows:**
- User Input: The user types a question in Streamlit.

- Translation: The Agent sends the schema and question to Groq (Llama 3).

- Execution: The LLM returns SQL, which is executed against DuckDB.

- Visualization: Results are converted to a Pandas DataFrame and rendered using Seaborn/Matplotlib.

- Alerting: Separately, the KPI engine computes daily aggregations and pushes alerts via Webhooks if thresholds are breached.

The agent was built using the following stack:

Frontend - Streamlit for the rapid UI development and native support for dataframes. This also helped with the session state management, allowing me to include an option to filter between graph types. (Bar chart, Line chart and boxplot).

Database - DuckDB, would've also worked with SQLite.

LLM - Groq API for the low latency and free API usage for personal projects.

Orchestration - Langchain to handle the prompt templating and connection to the LLM.

Visualization - Matplotlib and Seaborn because of the personalization options it gives and I was confortable working with those since I already used them extensivily in previous personal projects.

## Sample Queries and visualization

- Which product has the highest TPV?
![Highest_TPV](https://github.com/user-attachments/assets/2692a662-82a6-42b5-b473-1506deea3101)

- How do weekdays influence TPV?
![Weekday](https://github.com/user-attachments/assets/d8ec5997-d88b-4142-bfff-741e90d0dc8c)

- Which segment has the highest average TPV? And the highest Average Ticket?
![HighestTPV](https://github.com/user-attachments/assets/447594aa-0897-47dd-a540-01a4241a3cfe)


- Which anticipation method is most used by individuals and by businesses?
![Anticipation](https://github.com/user-attachments/assets/7eda7b32-eb04-4ecc-8b43-a497b28604d6)

## How to use
**Repository layout**
- `main.py` — Streamlit app UI
- `agent.py` — LLM prompt + query runner (returns SQL and pandas DataFrame)
- `kpis.py` - KPIs module.
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
GROQ_API_KEY=your_api_key_here
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



## KPI tool (Daily TPV & Alerts)
- Start the app as described above and open the sidebar by clicking in the top left of the screen to see "Daily KPIs & Alerts" section.
- UI controls:
  - `KPI date`: pick the date to evaluate (defaults to today when left empty).
  - `Alert threshold`: a fractional threshold (e.g., `0.25` = 25%). Set up the Lower and Upper ends of the threshold and the agent will Trigger if it see any changes that go over or under the limits.
  - `Webhook URL`: optional; if provided, you can click "Send KPI Alert" after a trigger fires.
- Click `Run KPIs` to compute TPV and view percentage variations vs D-1, D-7 and D-30. If any variation exceeds the threshold you'll see a warning and can send the alert.
<img width="1876" height="945" alt="image" src="https://github.com/user-attachments/assets/85d251dc-fe22-4f2a-a89d-df170958f30d" />




