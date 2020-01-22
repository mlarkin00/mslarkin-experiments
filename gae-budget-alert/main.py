import base64
import json
import os
import logging
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

PROJECT_ID = os.getenv('GCP_PROJECT')
APP_NAME = f"{PROJECT_ID}"

#Which alert threshold should trigger the shutdown (e.g. 100% of set budget)
TRIGGER_THRESHOLD = 1.0

def check_app(data, context):
    """
    Checks Budget Alert Pub/Sub message and disables App Engine
    if costs have exceeded the desired budget
    """
    
    #Extract relevant Pub/Sub message content - (Message format: https://cloud.google.com/billing/docs/how-to/budgets#notification_format)
  
    pubsub_data = base64.b64decode(data['data']).decode('utf-8')
    pubsub_json = json.loads(pubsub_data)

    cost_amount = pubsub_json['costAmount']
    budget_amount = pubsub_json['budgetAmount']
    budget_name = pubsub_json['budgetDisplayName']
    alert_threshold = pubsub_json['alertThresholdExceeded']
    
    # Check if we've hit the set limit (alert_threshold = .8 for 80%, 1.0 for 100%, etc.)
    if alert_threshold < TRIGGER_THRESHOLD:
        print(
            f'No action necessary at {alert_threshold} for {budget_name}.\n'
            f'Current Cost: {cost_amount}\n'
            f'Budget Amount: {budget_amount}'
            )
        return
    
    # Get the Apps object (http://googleapis.github.io/google-api-python-client/docs/dyn/appengine_v1.apps.html)
    appengine = discovery.build(
        'appengine',
        'v1',
        cache_discovery=False,
        credentials=GoogleCredentials.get_application_default()
    )
    apps = appengine.apps()

    # Get the current servingStatus 
    current_status = __get_app_status(APP_NAME, apps)
    
    print(f'Current servingStatus: {current_status}')

    # If app is serving, disable it
    if current_status == "SERVING":
        logging.warning(
            f'Budget threshold exceeded, disabling app {APP_NAME}\n'
            f'Budget Alert: {budget_name}\n'
            f'Budget Threshold: {alert_threshold}\n'
            f'Budget Amount: {budget_amount}\n'
            f'Current Cost: {cost_amount}'
        )
        __toggle_app(APP_NAME, apps, "USER_DISABLED")
    else:
        print(
            f'Budget threshold exceeded, but {APP_NAME} is already disabled\n'
            f'Budget Alert: {budget_name}'
            )
        return

    return

def __get_app_status(app_name, apps):
    """
    Get the current serving status of the app
    """
    app = apps.get(appsId=app_name).execute()
    return app['servingStatus']

def __toggle_app(app_name, apps, set_state):
    """
    Enables or Disables the app, depending on set_state
    """
    body = {'servingStatus': set_state}
    app = apps.patch(appsId=app_name, updateMask='serving_status', body=body).execute()
    return