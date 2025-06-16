to initialize database :python main.py setup-db |||||||||
to start the scraper   :python main.py run-scraper  |||||||||
to test the digitaltwin: python main.py run-simulation --meter-id <YOUR_METER_ID> --model <YOUR_MODEL_NAME> --duration-hours <HOURS_TO_PREDICT> --training-hours <HISTORICAL_TRAINING_HOURS> |||||||| example : python main.py run-simulation --meter-id meter_001 --model baseline_model --duration-hours 24 --training-hours 168 ||||||
to run the Backend     :python main.py api-server  |||||||||
envirnoment setup : 1) python -m venv venv |||||||||| 2) source venv/Scripts/activate |||||||||| 3) pip install Flask Flask-Cors psycopg2-binary pytz selenium webdriver-manager
