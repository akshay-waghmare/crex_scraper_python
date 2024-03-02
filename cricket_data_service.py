import requests
import json
import requests
import json

def get_bearer_token():
    # Define the URL of the token endpoint
    token_url = "http://localhost:8099/token/generate-token"

    # Define the credentials required to obtain the token (if needed)
    credentials = {
    "username": "tanmay",
    "password": "tanmay"
    }

    try:
        # Send a POST request to the token endpoint to obtain the token
        response = requests.post(token_url, json=credentials)

        # Check the response status code
        if response.status_code == 200:
            # Parse the JSON response to get the token
            token_data = response.json()
            return token_data.get("token")
        else:
            print(f"Failed to obtain bearer token. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")



def send_cricket_data_to_service(data, bearer_token,url):
    # Define the URL of the service where you want to send the data
    service_url = "http://localhost:8099/cricket-data"

    # Define the headers with the bearer token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }

    # Convert the data to JSON (assuming data is a dictionary)
    #json_data = json.dumps(data)
    json_payload = {}
    try:
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
            
            
        print("url to be sent back" , url)
        print("filtered data to be sent back" , json_payload)
        
        # Send the POST request to the service
        response = requests.post(service_url, headers=headers, json=json_payload)

        # Check the response status code
        if response.status_code == 200:
            print("Data sent successfully!")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        
def add_live_matches(data, bearer_token):
    # Define the URL of the service where you want to send the data
    service_url = "http://localhost:8099/cricket-data/add-live-matches"

    # Define the headers with the bearer token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bearer_token}"
    }

    try:
        # Convert the data to a JSON array
        payload = json.dumps(data)

        # Send the POST request to the service
        response = requests.post(service_url, headers=headers, data=payload)

        # Check the response status code
        if response.status_code == 200:
            print("Data sent successfully!")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        