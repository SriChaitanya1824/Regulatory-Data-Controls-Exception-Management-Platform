from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from platform_client import execute_controls
with DAG("governance_control_execution",start_date=datetime(2026,1,1),schedule="0 2 * * *",catchup=False,max_active_runs=1,tags=["governance","controls"]) as dag:
    PythonOperator(task_id="execute_active_controls",python_callable=execute_controls)
