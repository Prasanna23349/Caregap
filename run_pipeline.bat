set PYTHONIOENCODING=utf-8
call ..\.venv\Scripts\activate.bat
python bcs_step1_runner.py
python persona_graph_builder.py
python bcs_ehr_ingestion.py
python bcs_step2_matching.py
python bcs_step3_inherit.py
python bcs_step4_hedis_validate.py
