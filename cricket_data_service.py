import requests
import json
import requests
import json
import os
import logging 

logging.basicConfig(filename='crex_scraper.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_bearer_token():
    # Define the URL of the token endpoint
    token_url = os.getenv('TOKEN_URL', 'http://139.59.34.101:8099/token/generate-token')


    # Define the credentials required to obtain the token (if needed)
    credentials = {
    "username": "tanmay",
    "password": "tanmay"
    }

    try:
        logging.info("Requesting bearer token from token endpoint.")
        # Send a POST request to the token endpoint to obtain the token
        response = requests.post(token_url, json=credentials)

        # Check the response status code
        if response.status_code == 200:
            # Parse the JSON response to get the token
            token_data = response.json()
            logging.info("Bearer token obtained successfully.")
            return token_data.get("token")
        else:
            logging.error(f"Failed to obtain bearer token. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while obtaining bearer token: {str(e)}")



def send_cricket_data_to_service(data, bearer_token,url):
    # Define the URL of the service where you want to send the data
    service_url = os.getenv('SERVICE_URL', 'http://139.59.34.101:8099/cricket-data')

    # Define the headers with the bearer token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }

    # Convert the data to JSON (assuming data is a dictionary)
    #json_data = json.dumps(data)
    json_payload = {}
    try:
        logging.info("Preparing data to send to the service.")
        #filter data before sending  only non None values are sent
        if isinstance(data, list) :
            filtered_data = [
            {k: v for k, v in item.items() if v is not None} for item in data
        ]
            json_payload = {"data": filtered_data, "url": url}
            print("json_payload to be sent back for test match " , json_payload)
        else : 
            filtered_data = {k: v for k, v in data.items() if v is not None}
            filtered_data['url'] = url
            json_payload = filtered_data
            
            
        logging.info(f"Sending data to service URL: {service_url}")
        logging.debug(f"Payload: {json_payload}")
        
        # Send the POST request to the service
        response = requests.post(service_url, headers=headers, json=json_payload)

        # Check the response status code
        if response.status_code == 200:
            logging.info("Data sent successfully to the service.")
        else:
            logging.error(f"Failed to send data. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while sending data: {str(e)}")
        
def add_live_matches(data, bearer_token):
    # Define the URL of the service where you want to send the data
    service_url = os.getenv('ADD_LIVE_MATCHES_URL', 'http://139.59.34.101:8099/cricket-data/add-live-matches')
    
    # Define the headers with the bearer token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }

    try:
        # Convert the data to a JSON array
        payload = json.dumps(data)
        logging.info(f"Payload: {payload}")
        # Send the POST request to the service
        response = requests.post(service_url, headers=headers, data=payload)

        # Check the response status code
        if response.status_code == 200:
            logging.info("Live matches data added successfully.")
        else:
             logging.error(f"Failed to add live matches data. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"An error occurred while adding live matches data: {str(e)}")
        