import re
import os
import duckdb
import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

_llm = None

def get_llm():
    """Return a ChatGroq client created from environment variables or None if no API key."""
    global _llm
    if _llm is not None:
        return _llm

    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    if api_key is None:
        return None

    _llm = ChatGroq(model=model, api_key=api_key)
    return _llm

def get_db_connection():
    return duckdb.connect("cloudwalk.db", read_only=True)

system_template = """
You are a data analyst assistant. Your job is to translate natural language questions 
into SQL queries for DuckDB, based on this table:

Table name: transactions
Columns:
 - day (DATE/TIMESTAMP)
 - entity (STRING)
 - product (STRING)
 - price_tier (STRING)
 - anticipation_method (STRING)
 - nitro_or_d0 (STRING)
 - payment_method (STRING)
 - installments (INTEGER)
 - amount_transacted (DOUBLE) rounded to 2 decimal places and representing monetary values
 - quantity_transactions (INTEGER)
 - quantity_of_merchants (INTEGER)
 - week_day (INTEGER)
 - is_weekday (STRING)
 - week_day_name (STRING)

Rules
 - ONLY output SQL without markdown quotations.
 - Do NOT add explanation.
 - Use valid DuckDB SQL.
 - Use the column `amount_transacted` for monetary aggregations (there is no `amount` column).
 - If the question is about weekdays, use the average of `amount_transacted` per weekday.
 - When asked about the "highest" or "lowest" values, use ORDER BY and LIMIT to get more than 1 result for comparison.
 - When asked something "by x and by y", show both.
"""

prompt = PromptTemplate(
    template=system_template + "\nQuestion: {question}\nSQL:",
    input_variables=["question"]
)

# We will build the pipeline at call time because the LLM is created lazily
def _generate_sql_from_llm(question: str):
    llm = get_llm()
    sql_generator = prompt | llm | StrOutputParser()
    raw = sql_generator.invoke({"question": question})
    print(raw)
    return raw, None

def run_query(question: str):
    """Generate SQL from the LLM (or accept raw SQL), run it in DuckDB, return results.

    Behavior:
    - If `question` starts with `SQL:` (case-insensitive), treat the rest as raw SQL and run it.
    - Otherwise, attempt to generate SQL with the LLM. If `GROQ_API_KEY` is not present,
      return a clear error message instructing how to set it.
    """

    # Support raw SQL passthrough for development and testing
    if isinstance(question, str) and question.strip().lower().startswith("sql:"):
        sql = question.strip()[len("sql:"):].strip()
    else:
        raw, err = _generate_sql_from_llm(question)
        if err is not None:
            return "", err
        if raw is None:
            return "", "❌ LLM did not return any SQL"

        sql = str(raw).strip()

    # This is a hardcoded removal of the markdown quotations. Since I made it explicit in the system prompt, 
    # it is not necessary to have it here anymore. Leaving it in case I notice its better to state it here 
    # than in the system_template query.
    '''Remove Markdown code fences if present (```sql ... ``` or ``` ... ```)
    m = re.search(r"```(?:sql\n)?(.*?)```", sql, re.S | re.I)
    if m:
        sql = m.group(1).strip() # testar varios prompts diferentes pra ver como reage com isso ou com a diferença direta no prompt.

    Also remove any leading 'SQL:' labels that might appear in LLM output
    if sql.lower().startswith("sql:"):
        sql = sql[len("sql:"):].strip()'''

    # Final whitespace cleanup
    sql = sql.strip('\n')
    con = duckdb.connect("cloudwalk.db", read_only=True)
    try:
        # Use pandas to get a DataFrame result for easier display/plotting
        df = pd.read_sql_query(sql, con)
        return sql, df
    except Exception as e:
        # Return the SQL and the error message so the UI can show it
        return sql, f"❌ SQL Error: {str(e)}"
    finally:
        con.close()