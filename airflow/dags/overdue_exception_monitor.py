from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from platform_client import overdue
with DAG("overdue_exception_monitor",start_date=datetime(2026,1,1),schedule="0 6 * * 1-5",catchup=False,max_active_runs=1,tags=["governance","exceptions"]) as dag:
    PythonOperator(task_id="find_unresolved_overdue_exceptions",python_callable=overdue)
