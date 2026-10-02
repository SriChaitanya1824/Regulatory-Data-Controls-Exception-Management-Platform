from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from platform_client import execute_controls,snapshot_dashboard,overdue
with DAG("monthly_exception_review",start_date=datetime(2026,1,1),schedule="0 4 1 * *",catchup=False,max_active_runs=1,tags=["governance","reporting"]) as dag:
    run=PythonOperator(task_id="execute_governance_controls",python_callable=execute_controls)
    late=PythonOperator(task_id="identify_overdue_exceptions",python_callable=overdue)
    report=PythonOperator(task_id="persist_monthly_summary",python_callable=snapshot_dashboard)
    run >> late >> report
